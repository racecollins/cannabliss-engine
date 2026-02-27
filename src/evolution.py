"""Evolutionary candidate generation and scoring for playlist curation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import pvariance

from src.selection import Track, select_tracks_from_tracks


@dataclass(frozen=True)
class ScoreWeights:
    novelty: float = 1.0
    diversity: float = 1.0
    cohesion: float = 1.0
    freshness: float = 0.5


@dataclass
class Candidate:
    id: str
    seed: int | None
    tracks: list[Track]
    score: float = 0.0
    breakdown: dict[str, float] | None = None


def track_id_from_uri(uri: str) -> str:
    if ":" in uri:
        return uri.rsplit(":", 1)[-1]
    return uri


def primary_artist(track: Track) -> str:
    return (track.artists.split(",")[0].strip().lower() or "unknown")


def parse_iso8601(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def gather_recent_track_ids(history_runs: list[dict], history_weeks: int) -> set[str]:
    if history_weeks <= 0:
        return set()
    blocked: set[str] = set()
    for run in history_runs[-history_weeks:]:
        ids = run.get("track_ids", [])
        if isinstance(ids, list):
            blocked.update(str(i) for i in ids)
    return blocked


def candidate_seed(seed_base: int | None, index: int) -> int | None:
    if seed_base is None:
        return None
    return seed_base + index


def generate_candidates(
    tracks: list[Track],
    mode: str,
    count: int,
    candidates: int,
    seed_base: int | None,
    history_runs: list[dict],
    history_weeks: int,
    max_tracks_per_artist: int,
    fresh_days_1: int,
    fresh_days_2: int,
) -> list[Candidate]:
    """Create K candidates by varying seed around a stable base."""
    out: list[Candidate] = []
    for idx in range(candidates):
        seed = candidate_seed(seed_base, idx)
        selected, _meta = select_tracks_from_tracks(
            tracks,
            mode=mode,
            count=count,
            seed=seed,
            history_runs=history_runs,
            history_weeks=history_weeks,
            max_tracks_per_artist=max_tracks_per_artist,
            fresh_days_1=fresh_days_1,
            fresh_days_2=fresh_days_2,
        )
        out.append(Candidate(id=f"cand-{idx + 1}", seed=seed, tracks=selected))
    return out


def novelty_score(candidate: Candidate, recent_ids: set[str]) -> float:
    if not candidate.tracks:
        return 0.0
    if not recent_ids:
        return 1.0
    novel = 0
    for t in candidate.tracks:
        if track_id_from_uri(t.uri) not in recent_ids:
            novel += 1
    return novel / len(candidate.tracks)


def diversity_score(candidate: Candidate) -> float:
    if not candidate.tracks:
        return 0.0
    artists = {primary_artist(t) for t in candidate.tracks}
    return len(artists) / len(candidate.tracks)


def cohesion_score(candidate: Candidate, audio_features: dict[str, dict]) -> float:
    """Higher score for lower within-candidate feature variance."""
    values: dict[str, list[float]] = {
        "energy": [],
        "danceability": [],
        "valence": [],
        "tempo": [],
    }
    for t in candidate.tracks:
        tid = track_id_from_uri(t.uri)
        feat = audio_features.get(tid)
        if not feat:
            continue
        for key in values:
            raw = feat.get(key)
            if isinstance(raw, (int, float)):
                values[key].append(float(raw))

    if not values["energy"]:
        return 0.0

    var_sum = 0.0
    for key, vals in values.items():
        if len(vals) >= 2:
            var = pvariance(vals)
            if key == "tempo":
                var /= 10000.0
            var_sum += var
    return 1.0 / (1.0 + var_sum)


def freshness_score(candidate: Candidate, now: datetime | None = None) -> float:
    if not candidate.tracks:
        return 0.0
    current = now or datetime.now(timezone.utc)
    total = 0.0
    for t in candidate.tracks:
        added = parse_iso8601(t.added_at)
        if added is None:
            total += 0.0
            continue
        age_days = max(0, int((current - added).total_seconds() // 86400))
        if age_days <= 30:
            total += 1.0
        elif age_days <= 180:
            total += 0.6
        else:
            total += 0.2
    return total / len(candidate.tracks)


def score_candidate(
    candidate: Candidate,
    recent_ids: set[str],
    audio_features: dict[str, dict],
    weights: ScoreWeights,
    now: datetime | None = None,
) -> Candidate:
    novelty = novelty_score(candidate, recent_ids)
    diversity = diversity_score(candidate)
    cohesion = cohesion_score(candidate, audio_features)
    freshness = freshness_score(candidate, now=now)
    score = (
        weights.novelty * novelty
        + weights.diversity * diversity
        + weights.cohesion * cohesion
        + weights.freshness * freshness
    )
    candidate.score = score
    candidate.breakdown = {
        "novelty": novelty,
        "diversity": diversity,
        "cohesion": cohesion,
        "freshness": freshness,
        "w_novelty": weights.novelty,
        "w_diversity": weights.diversity,
        "w_cohesion": weights.cohesion,
        "w_freshness": weights.freshness,
        "total": score,
    }
    return candidate


def score_candidates(
    candidates: list[Candidate],
    history_runs: list[dict],
    history_weeks: int,
    audio_features: dict[str, dict],
    weights: ScoreWeights,
    now: datetime | None = None,
) -> list[Candidate]:
    recent_ids = gather_recent_track_ids(history_runs, history_weeks)
    return [score_candidate(c, recent_ids, audio_features, weights, now=now) for c in candidates]


def choose_winner(candidates: list[Candidate]) -> Candidate:
    if not candidates:
        raise ValueError("No candidates to choose from")
    return max(candidates, key=lambda c: c.score)


def serialize_candidate(candidate: Candidate) -> dict:
    return {
        "id": candidate.id,
        "seed": candidate.seed,
        "score": candidate.score,
        "breakdown": candidate.breakdown or {},
        "track_ids": [track_id_from_uri(t.uri) for t in candidate.tracks],
    }


def append_evolve_log(
    path: str,
    mode: str,
    candidates: list[Candidate],
    winner: Candidate,
    now: datetime | None = None,
) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    payload = {
        "timestamp": (now or datetime.now(timezone.utc)).isoformat(),
        "mode": mode,
        "candidates": [serialize_candidate(c) for c in candidates],
        "winner_id": winner.id,
        "winner_score": winner.score,
    }
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload) + "\n")

