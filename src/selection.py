"""Selection logic: filter, deduplicate, and pick tracks."""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class Track:
    uri: str
    name: str
    artists: str
    added_at: str  # ISO-8601


def _track_id(uri: str) -> str:
    if ":" in uri:
        return uri.rsplit(":", 1)[-1]
    return uri


def _primary_artist(track: Track) -> str:
    primary = track.artists.split(",")[0].strip().lower()
    return primary or "unknown"


def _parse_added_at(added_at: str) -> datetime | None:
    if not added_at:
        return None
    try:
        return datetime.fromisoformat(added_at.replace("Z", "+00:00"))
    except ValueError:
        return None


def _age_days(added_at: str, now: datetime) -> int:
    parsed = _parse_added_at(added_at)
    if not parsed:
        return 36500
    return max(0, int((now - parsed).total_seconds() // 86400))


def parse_tracks(raw_items: list[dict]) -> list[Track]:
    """Parse raw Spotify playlist items into Track objects.

    Filters out:
      - null / missing track entries
      - non-track types (episodes, podcasts)
      - local files
      - entries without a URI
    """
    tracks: list[Track] = []
    for item in raw_items:
        # Legacy `/tracks` responses return `track`; `/items` returns `item`.
        t = item.get("track")
        if not t:
            t = item.get("item")
        if not t:
            continue
        if t.get("type") != "track":
            continue
        # Local-flag can be present on container item and/or nested item.
        if item.get("is_local", False) or t.get("is_local", False):
            continue
        uri = t.get("uri")
        if not uri:
            continue

        name = t.get("name", "Unknown")
        artists = ", ".join(a.get("name", "?") for a in t.get("artists", []))
        added_at = item.get("added_at", "")

        tracks.append(Track(uri=uri, name=name, artists=artists, added_at=added_at))

    return tracks


def deduplicate(tracks: list[Track]) -> list[Track]:
    """Remove duplicate track URIs, keeping the most recently added instance."""
    seen: dict[str, Track] = {}
    for t in tracks:
        if t.uri not in seen or t.added_at > seen[t.uri].added_at:
            seen[t.uri] = t
    return list(seen.values())


def select_recent(tracks: list[Track], count: int) -> list[Track]:
    """Select the most recently added `count` tracks."""
    sorted_tracks = sorted(tracks, key=lambda t: t.added_at, reverse=True)
    return sorted_tracks[:count]


def load_history(path: str = "data/history.json") -> list[dict]:
    """Load run history from disk, creating an empty file if missing."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    if not os.path.exists(path):
        save_history([], path)
        return []

    try:
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return []

    runs = payload.get("runs")
    if isinstance(runs, list):
        return runs
    return []


def save_history(runs: list[dict], path: str = "data/history.json") -> None:
    """Persist run history to disk."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    payload = {"runs": runs}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def append_history(
    selected: list[Track],
    mode: str,
    seed: int | None,
    path: str = "data/history.json",
    now: datetime | None = None,
) -> None:
    """Append the current run's selected tracks to history."""
    runs = load_history(path)
    ts = (now or datetime.now(timezone.utc)).isoformat()
    runs.append(
        {
            "timestamp": ts,
            "mode": mode,
            "seed": seed,
            "track_ids": [_track_id(t.uri) for t in selected],
        }
    )
    save_history(runs, path)


def filter_by_history(tracks: list[Track], runs: list[dict], history_weeks: int) -> list[Track]:
    """Exclude tracks present in the most recent `history_weeks` runs."""
    if history_weeks <= 0 or not runs:
        return list(tracks)

    recent_runs = runs[-history_weeks:]
    blocked: set[str] = set()
    for run in recent_runs:
        ids = run.get("track_ids", [])
        if isinstance(ids, list):
            blocked.update(str(i) for i in ids)

    return [t for t in tracks if _track_id(t.uri) not in blocked]


def enforce_artist_cap(
    tracks: list[Track],
    count: int,
    max_tracks_per_artist: int,
) -> tuple[list[Track], int]:
    """Apply per-primary-artist cap, relaxing gradually if needed."""
    if not tracks:
        return [], max_tracks_per_artist

    cap = max(1, max_tracks_per_artist)
    while cap <= count:
        selected: list[Track] = []
        per_artist: dict[str, int] = {}

        for t in tracks:
            artist = _primary_artist(t)
            used = per_artist.get(artist, 0)
            if used >= cap:
                continue
            selected.append(t)
            per_artist[artist] = used + 1
            if len(selected) >= count:
                return selected, cap

        cap += 1

    return tracks[:count], max(1, max_tracks_per_artist)


def weighted_sample(
    tracks: list[Track],
    count: int,
    seed: int | None = None,
    fresh_days_1: int = 30,
    fresh_days_2: int = 180,
    now: datetime | None = None,
) -> list[Track]:
    """Weighted sample without replacement. More recent tracks weigh higher."""
    rng = random.Random(seed)
    if len(tracks) <= count:
        ranked = weighted_rank(tracks, rng, fresh_days_1, fresh_days_2, now)
        return ranked

    ranked = weighted_rank(tracks, rng, fresh_days_1, fresh_days_2, now)
    return ranked[:count]


def weighted_rank(
    tracks: list[Track],
    rng: random.Random,
    fresh_days_1: int,
    fresh_days_2: int,
    now: datetime | None = None,
) -> list[Track]:
    """Return a weighted random ranking of tracks (highest-priority first)."""
    current = now or datetime.now(timezone.utc)
    scored: list[tuple[float, Track]] = []
    for t in tracks:
        age = _age_days(t.added_at, current)
        if age <= fresh_days_1:
            weight = 3.0
        elif age <= fresh_days_2:
            weight = 2.0
        else:
            weight = 1.0

        # Efraimidis-Spirakis key for weighted sampling without replacement.
        key = rng.random() ** (1.0 / weight)
        scored.append((key, t))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [t for _, t in scored]


def select_random(
    tracks: list[Track],
    count: int,
    seed: int | None = None,
    max_tracks_per_artist: int = 2,
    fresh_days_1: int = 30,
    fresh_days_2: int = 180,
    now: datetime | None = None,
) -> tuple[list[Track], int]:
    """Weighted random selection plus artist-cap enforcement."""
    rng = random.Random(seed)
    ranked = weighted_rank(tracks, rng, fresh_days_1, fresh_days_2, now)
    return enforce_artist_cap(ranked, count, max_tracks_per_artist)


def select_recent_with_cap(
    tracks: list[Track],
    count: int,
    max_tracks_per_artist: int,
) -> tuple[list[Track], int]:
    ranked = sorted(tracks, key=lambda t: t.added_at, reverse=True)
    return enforce_artist_cap(ranked, count, max_tracks_per_artist)


def _select_from_pool(
    tracks: list[Track],
    mode: str,
    count: int,
    seed: int | None,
    max_tracks_per_artist: int,
    fresh_days_1: int,
    fresh_days_2: int,
    now: datetime | None,
) -> tuple[list[Track], int]:
    if mode == "recent":
        return select_recent_with_cap(tracks, count, max_tracks_per_artist)
    return select_random(
        tracks,
        count,
        seed=seed,
        max_tracks_per_artist=max_tracks_per_artist,
        fresh_days_1=fresh_days_1,
        fresh_days_2=fresh_days_2,
        now=now,
    )


def select_tracks_from_tracks(
    tracks: list[Track],
    mode: str,
    count: int,
    seed: int | None = None,
    history_runs: list[dict] | None = None,
    history_weeks: int = 6,
    max_tracks_per_artist: int = 2,
    fresh_days_1: int = 30,
    fresh_days_2: int = 180,
    now: datetime | None = None,
) -> tuple[list[Track], dict]:
    """Select from prepared tracks with history and diversity constraints."""
    unique = deduplicate(tracks)
    if len(unique) < len(tracks):
        print(f"🔁 Deduplicated: {len(tracks)} → {len(unique)} unique tracks")

    history_runs = history_runs or []
    filtered = filter_by_history(unique, history_runs, history_weeks)
    used_history_filter = True
    if history_runs and len(filtered) < count:
        print(
            f"⚠️  History filter leaves {len(filtered)} tracks (requested {count}); "
            "relaxing history constraint."
        )
        filtered = unique
        used_history_filter = False

    if len(filtered) < count:
        print(f"⚠️  Only {len(filtered)} tracks available (requested {count})")

    selected, cap_used = _select_from_pool(
        filtered,
        mode,
        count,
        seed,
        max_tracks_per_artist,
        fresh_days_1,
        fresh_days_2,
        now,
    )
    if cap_used > max_tracks_per_artist:
        print(
            f"⚠️  Relaxed MAX_TRACKS_PER_ARTIST from {max_tracks_per_artist} to {cap_used} "
            "to reach target count."
        )

    meta = {
        "used_history_filter": used_history_filter,
        "artist_cap_used": cap_used,
    }
    return selected, meta


def select_random_legacy(tracks: list[Track], count: int, seed: int | None = None) -> list[Track]:
    """Legacy uniform sampler kept for compatibility in targeted tests if needed."""
    rng = random.Random(seed)
    if len(tracks) <= count:
        result = list(tracks)
        rng.shuffle(result)
        return result
    return rng.sample(tracks, count)


def select_tracks(
    raw_items: list[dict],
    mode: str,
    count: int,
    seed: int | None = None,
) -> list[Track]:
    """Full pipeline: parse → deduplicate → select."""
    tracks = parse_tracks(raw_items)
    print(f"📋 Parsed {len(tracks)} valid tracks")
    selected, _ = select_tracks_from_tracks(
        tracks,
        mode=mode,
        count=count,
        seed=seed,
    )
    return selected
