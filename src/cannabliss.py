"""Cannabliss-specific curated playlist builder and state tracking."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timezone


MAJOR_FRONT_QUEUE_DAYS = 21
MAJOR_TOP_10_FRESH_TARGET = 8
MAJOR_TOP_10_CARRYOVER_LIMIT = 2


@dataclass
class CannablissTrack:
    uri: str
    name: str
    artists: str
    added_at: str
    source_tags: set[str] = field(default_factory=set)
    current_position: int | None = None
    popularity: int | None = None
    release_date: str = ""


@dataclass
class CannablissBuildResult:
    ordered_tracks: list[CannablissTrack]
    zones: dict[str, list[CannablissTrack]]
    summary: dict[str, list[str]]
    new_track_count: int
    update_mode: str


@dataclass(frozen=True)
class ListeningSignals:
    top_track_ids: frozenset[str] = frozenset()
    recently_played_ids: frozenset[str] = frozenset()
    top_tracks_boost: float = 0.35
    recently_played_boost: float = 0.25


def parse_source_items(
    raw_items: list[dict],
    *,
    source_tag: str,
    current_order: bool = False,
) -> list[CannablissTrack]:
    """Parse Spotify playlist items into CannablissTrack objects."""
    tracks: list[CannablissTrack] = []
    for index, item in enumerate(raw_items, start=1):
        nested = item.get("track") or item.get("item")
        if not nested or nested.get("type") != "track":
            continue
        if item.get("is_local", False) or nested.get("is_local", False):
            continue
        uri = nested.get("uri")
        if not uri:
            continue

        release_date = (((nested.get("album") or {}).get("release_date")) or "").strip()
        popularity = nested.get("popularity")
        artists = ", ".join(a.get("name", "?") for a in nested.get("artists", []))
        tracks.append(
            CannablissTrack(
                uri=uri,
                name=nested.get("name", "Unknown"),
                artists=artists,
                added_at=item.get("added_at", ""),
                source_tags={source_tag},
                current_position=index if current_order else None,
                popularity=popularity if isinstance(popularity, int) else None,
                release_date=release_date,
            )
        )
    return tracks


def merge_track_sets(track_sets: list[list[CannablissTrack]]) -> dict[str, CannablissTrack]:
    """Merge track metadata by URI, preserving the richest combined view."""
    merged: dict[str, CannablissTrack] = {}
    for tracks in track_sets:
        for track in tracks:
            existing = merged.get(track.uri)
            if existing is None:
                merged[track.uri] = CannablissTrack(
                    uri=track.uri,
                    name=track.name,
                    artists=track.artists,
                    added_at=track.added_at,
                    source_tags=set(track.source_tags),
                    current_position=track.current_position,
                    popularity=track.popularity,
                    release_date=track.release_date,
                )
                continue

            existing.source_tags.update(track.source_tags)
            if track.current_position is not None:
                if existing.current_position is None or track.current_position < existing.current_position:
                    existing.current_position = track.current_position
            if track.added_at > existing.added_at:
                existing.added_at = track.added_at
            if track.popularity is not None:
                existing.popularity = max(existing.popularity or 0, track.popularity)
            if track.release_date and (
                not existing.release_date or track.release_date > existing.release_date
            ):
                existing.release_date = track.release_date
    return merged


def _dedupe_song_variants(tracks_by_uri: dict[str, CannablissTrack]) -> dict[str, CannablissTrack]:
    """Collapse obvious same-song variants for Cannabliss ordering.

    We keep the best representative per primary-artist/title signature while
    preserving all source tags gathered for that song.
    """
    best_by_key: dict[str, CannablissTrack] = {}
    for track in tracks_by_uri.values():
        key = _song_key(track)
        existing = best_by_key.get(key)
        if existing is None:
            best_by_key[key] = track
            continue

        if _variant_rank(track) > _variant_rank(existing):
            track.source_tags.update(existing.source_tags)
            if track.current_position is None:
                track.current_position = existing.current_position
            best_by_key[key] = track
        else:
            existing.source_tags.update(track.source_tags)
            if existing.current_position is None:
                existing.current_position = track.current_position

    return {track.uri: track for track in best_by_key.values()}


def load_cannabliss_state(path: str = "data/cannabliss_state.json") -> dict:
    """Load Cannabliss state from disk, creating an empty payload if missing."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    if not os.path.exists(path):
        payload = {"runs": []}
        save_cannabliss_state(payload, path)
        return payload

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {"runs": []}

    if not isinstance(data, dict):
        return {"runs": []}
    runs = data.get("runs")
    if not isinstance(runs, list):
        data["runs"] = []
    return data


def save_cannabliss_state(payload: dict, path: str = "data/cannabliss_state.json") -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def append_cannabliss_run(
    result: CannablissBuildResult,
    *,
    path: str = "data/cannabliss_state.json",
    now: datetime | None = None,
) -> None:
    payload = load_cannabliss_state(path)
    runs = payload.setdefault("runs", [])
    runs.append(
        {
            "timestamp": (now or datetime.now(timezone.utc)).isoformat(),
            "track_ids": [track_id(t.uri) for t in result.ordered_tracks],
            "new_track_count": result.new_track_count,
            "summary": result.summary,
            "zones": {
                zone: [track_id(t.uri) for t in tracks]
                for zone, tracks in result.zones.items()
            },
        }
    )
    save_cannabliss_state(payload, path)


def build_cannabliss_playlist(
    *,
    master_tracks: list[CannablissTrack],
    current_tracks: list[CannablissTrack],
    feeder_tracks: list[CannablissTrack],
    hall_tracks: list[CannablissTrack],
    target_size: int,
    weekly_insertions: int,
    update_mode: str = "major",
    micro_refresh_count: int = 5,
    max_tracks_per_artist: int = 2,
    max_hall_returns: int = 3,
    listening_signals: ListeningSignals | None = None,
    now: datetime | None = None,
) -> CannablissBuildResult:
    """Build the ordered Cannabliss curated playlist."""
    current = now or datetime.now(timezone.utc)
    signals = listening_signals or ListeningSignals()
    merged = _dedupe_song_variants(merge_track_sets([master_tracks, current_tracks, feeder_tracks, hall_tracks]))
    current_order = [track.uri for track in sorted(current_tracks, key=lambda t: t.current_position or 10**9)]
    current_ids = set(current_order)
    is_initial_build = not current_order

    incumbents = [merged[uri] for uri in current_order if uri in merged]
    fresh_candidates = [
        track for uri, track in merged.items()
        if uri not in current_ids and "hall" not in track.source_tags
    ]
    hall_returners = [
        track for uri, track in merged.items()
        if uri not in current_ids and "hall" in track.source_tags
    ]
    library_candidates = [track for uri, track in merged.items() if uri not in current_ids]

    insertion_goal = weekly_insertions if update_mode == "major" else micro_refresh_count
    desired_new = min(
        target_size,
        insertion_goal,
        len(fresh_candidates) + min(len(hall_returners), max_hall_returns),
    )
    selected_ids: set[str] = set()
    artist_counts: dict[str, int] = {}
    effective_target_size = target_size
    if update_mode == "micro" and not is_initial_build:
        effective_target_size = max(target_size, len(current_order)) + desired_new

    chosen_new = _plan_batch(
        fresh_candidates,
        desired_new,
        max_tracks_per_artist=max_tracks_per_artist,
        score_kind="new",
        listening_signals=signals,
        now=current,
    )

    hall_needed = max(0, desired_new - len(chosen_new))
    if hall_needed:
        chosen_new.extend(
            _plan_batch(
                hall_returners,
                min(hall_needed, max_hall_returns),
                max_tracks_per_artist=max_tracks_per_artist,
                score_kind="new",
                listening_signals=signals,
                now=current,
            )
        )

    new_ids = {track.uri for track in chosen_new}

    signaled_tracks = _top_ranked(
        [track for track in merged.values() if _has_listening_signal(track, signals)],
        40,
        score_kind="premium",
        now=current,
        listening_signals=signals,
    )
    fresh_ranked = _top_ranked(
        fresh_candidates,
        len(fresh_candidates),
        score_kind="new",
        now=current,
        listening_signals=signals,
    )
    front_queue_ranked = _top_ranked(
        _front_queue_candidates(list(merged.values()), now=current),
        len(merged),
        score_kind="new",
        now=current,
        listening_signals=signals,
    )
    incumbents_ranked = _top_ranked(
        incumbents,
        len(incumbents),
        score_kind="premium",
        now=current,
        listening_signals=signals,
    )
    top_10: list[CannablissTrack] = []
    if update_mode == "micro" and incumbents:
        # Micro refreshes should keep the playlist recognizable. Treat the
        # existing top 10 as the locked identity tier and let the smaller
        # movement budget play out below it.
        locked_top_10 = [
            track for track in incumbents if track.current_position is not None and track.current_position <= 10
        ]
        locked_top_10.sort(key=lambda track: track.current_position or 10**9)
        for track in locked_top_10:
            if track.uri in selected_ids:
                continue
            artist = _primary_artist(track.artists)
            if artist_counts.get(artist, 0) >= 1:
                continue
            selected_ids.add(track.uri)
            artist_counts[artist] = artist_counts.get(artist, 0) + 1
            top_10.append(track)
            if len(top_10) >= 10:
                break
    elif update_mode == "major" and not is_initial_build:
        prior_front_ids = set(current_order[:20])
        fresh_front_pool = _ordered_unique(
            [track for track in front_queue_ranked if track.uri not in prior_front_ids]
            + [track for track in fresh_ranked if track.uri not in prior_front_ids]
            + [track for track in chosen_new if track.uri not in prior_front_ids]
        )
        top_10.extend(
            _select_scored(
                fresh_front_pool,
                MAJOR_TOP_10_FRESH_TARGET,
                selected_ids,
                artist_counts,
                max_tracks_per_artist=1,
                score_kind="new",
                listening_signals=signals,
                now=current,
            )
        )
        carryover_pool = _ordered_unique(
            [track for track in signaled_tracks if track.uri in prior_front_ids]
            + [track for track in incumbents_ranked if track.uri in prior_front_ids]
        )
        top_10.extend(
            _select_scored(
                carryover_pool,
                min(MAJOR_TOP_10_CARRYOVER_LIMIT, 10 - len(top_10)),
                selected_ids,
                artist_counts,
                max_tracks_per_artist=1,
                score_kind="premium",
                listening_signals=signals,
                now=current,
            )
        )
    else:
        top_10.extend(
            _select_scored(
                signaled_tracks,
                10,
                selected_ids,
                artist_counts,
                max_tracks_per_artist=1,
                score_kind="premium",
                listening_signals=signals,
                now=current,
            )
        )
    if len(top_10) < 10:
        top_pool = _ordered_unique(
            front_queue_ranked
            + chosen_new
            + (fresh_ranked[:25] if is_initial_build else incumbents_ranked[:25])
            + signaled_tracks
        )
        top_10.extend(
            _select_scored(
                top_pool,
                10 - len(top_10),
                selected_ids,
                artist_counts,
                max_tracks_per_artist=1,
                score_kind="premium",
                listening_signals=signals,
                now=current,
            )
        )

    zone_11_25_primary = [track for track in chosen_new if track.uri not in selected_ids]
    if update_mode == "major":
        zone_11_25_primary = _ordered_unique(
            [track for track in front_queue_ranked if track.uri not in selected_ids]
            + [track for track in chosen_new if track.uri not in selected_ids]
            + [track for track in signaled_tracks if track.uri not in selected_ids]
        )

    zone_11_25 = _fill_zone(
        primary_tracks=zone_11_25_primary,
        fallback_tracks=[
            track
            for track in (
                fresh_ranked
                if is_initial_build or update_mode == "major"
                else incumbents_ranked
            )
            if track.uri not in selected_ids
        ],
        limit=15,
        selected_ids=selected_ids,
        artist_counts=artist_counts,
        max_tracks_per_artist=1,
        score_kind="new",
        listening_signals=signals,
        now=current,
    )

    discovery_limit = 15 if update_mode == "major" else min(15, max(3, desired_new))
    zone_26_40 = _fill_zone(
        primary_tracks=[track for track in chosen_new if track.uri not in selected_ids],
        fallback_tracks=[
            track
            for track in (fresh_ranked if is_initial_build else incumbents_ranked)
            if track.uri not in selected_ids
        ],
        limit=discovery_limit,
        selected_ids=selected_ids,
        artist_counts=artist_counts,
        max_tracks_per_artist=max(2, min(max_tracks_per_artist, 2)),
        score_kind="discovery",
        listening_signals=signals,
        now=current,
    )

    remaining_new_tracks = [track for track in chosen_new if track.uri not in selected_ids]
    if is_initial_build:
        stabilizer_new = _fill_zone(
            primary_tracks=remaining_new_tracks,
            fallback_tracks=[track for track in fresh_ranked if track.uri not in selected_ids],
            limit=10,
            selected_ids=selected_ids,
            artist_counts=artist_counts,
            max_tracks_per_artist=max(2, min(max_tracks_per_artist, 2)),
            score_kind="stabilizer",
            listening_signals=signals,
            now=current,
        )
        stabilizer_incumbents = []
    else:
        stabilizer_new = _select_scored(
            remaining_new_tracks,
            min(10, len(remaining_new_tracks)),
            selected_ids,
            artist_counts,
            max_tracks_per_artist=max(2, min(max_tracks_per_artist, 2)),
            score_kind="stabilizer",
            listening_signals=signals,
            now=current,
        )
        stabilizer_incumbents = _select_scored(
            [track for track in incumbents if track.uri not in selected_ids],
            max(0, 10 - len(stabilizer_new)),
            selected_ids,
            artist_counts,
            max_tracks_per_artist=max(2, min(max_tracks_per_artist, 2)),
            score_kind="stabilizer",
            listening_signals=signals,
            now=current,
        )
    zone_41_50 = _interleave_tracks(stabilizer_incumbents, stabilizer_new, 10)

    remaining_slots = max(
        0,
        effective_target_size - (
            len(top_10) + len(zone_11_25) + len(zone_26_40) + len(zone_41_50)
        ),
    )
    protected_uris = {track.uri for track in top_10 + zone_11_25 + zone_26_40 + zone_41_50}
    provisional_tail = _ordered_unique(
        [track for track in incumbents if track.uri not in protected_uris]
    )
    remainder = _prune_tail_candidates(
        provisional_tail,
        limit=remaining_slots,
        listening_signals=signals,
        now=current,
    )
    if len(remainder) < remaining_slots:
        remainder.extend(
            _select_scored(
                [track for track in library_candidates if track.uri not in selected_ids],
                remaining_slots - len(remainder),
                selected_ids,
                artist_counts,
                max_tracks_per_artist=max_tracks_per_artist,
                score_kind="library",
                listening_signals=signals,
                now=current,
            )
        )

    ordered = top_10 + zone_11_25 + zone_26_40 + zone_41_50 + remainder

    positions_before = {uri: index for index, uri in enumerate(current_order, start=1)}
    positions_after = {track.uri: index for index, track in enumerate(ordered, start=1)}
    top_10_before = current_order[:10]
    top_10_after = [track.uri for track in top_10]

    summary = {
        "update_mode": [update_mode],
        "added": [track_id(track.uri) for track in ordered if track.uri not in current_ids],
        "promoted": [
            track_id(uri)
            for uri, old_pos in positions_before.items()
            if uri in positions_after and positions_after[uri] < old_pos
        ],
        "held": [
            track_id(uri)
            for uri, old_pos in positions_before.items()
            if uri in positions_after and positions_after[uri] == old_pos
        ],
        "shifted_down": [
            track_id(uri)
            for uri, old_pos in positions_before.items()
            if uri in positions_after and positions_after[uri] > old_pos
        ],
        "removed": [track_id(uri) for uri in current_order if uri not in positions_after],
        "top_10_added": [
            track_id(uri) for uri in top_10_after if uri not in set(top_10_before)
        ],
        "top_10_removed": [
            track_id(uri) for uri in top_10_before if uri not in set(top_10_after)
        ],
        "top_20_added": [
            track_id(track.uri)
            for track in ordered[:20]
            if track.uri not in set(current_order[:20])
        ],
        "top_20_removed": [
            track_id(uri)
            for uri in current_order[:20]
            if uri not in {track.uri for track in ordered[:20]}
        ],
        "front_queue": [
            track_id(track.uri)
            for track in ordered[:25]
            if track.uri in {queued.uri for queued in front_queue_ranked}
        ],
        "retained": [
            track_id(uri) for uri in current_order if uri in positions_after
        ],
    }
    total_changed = len(set(summary["added"] + summary["removed"] + summary["promoted"]))
    summary["total_changed"] = [str(total_changed)]
    if update_mode == "micro":
        summary["micro_adjustments"] = [str(min(total_changed, insertion_goal))]

    return CannablissBuildResult(
        ordered_tracks=ordered,
        zones={
            "premium_current": top_10,
            "high_conviction": zone_11_25,
            "discovery": zone_26_40,
            "stabilizers": zone_41_50,
            "library": remainder,
        },
        summary=summary,
        new_track_count=sum(1 for track in ordered if track.uri in new_ids or track.uri not in current_ids),
        update_mode=update_mode,
    )


def _select_scored(
    tracks: list[CannablissTrack],
    limit: int,
    selected_ids: set[str],
    artist_counts: dict[str, int],
    *,
    max_tracks_per_artist: int,
    score_kind: str,
    listening_signals: ListeningSignals,
    now: datetime,
) -> list[CannablissTrack]:
    if limit <= 0:
        return []
    ordered = _top_ranked(tracks, len(tracks), score_kind, now, listening_signals)
    chosen: list[CannablissTrack] = []
    for track in ordered:
        if track.uri in selected_ids:
            continue
        artist = _primary_artist(track.artists)
        if artist_counts.get(artist, 0) >= max_tracks_per_artist:
            continue
        selected_ids.add(track.uri)
        artist_counts[artist] = artist_counts.get(artist, 0) + 1
        chosen.append(track)
        if len(chosen) >= limit:
            break
    return chosen


def _plan_batch(
    tracks: list[CannablissTrack],
    limit: int,
    *,
    max_tracks_per_artist: int,
    score_kind: str,
    listening_signals: ListeningSignals,
    now: datetime,
) -> list[CannablissTrack]:
    selected_ids: set[str] = set()
    artist_counts: dict[str, int] = {}
    return _select_scored(
        tracks,
        limit,
        selected_ids,
        artist_counts,
        max_tracks_per_artist=max_tracks_per_artist,
        score_kind=score_kind,
        listening_signals=listening_signals,
        now=now,
    )


def _fill_zone(
    *,
    primary_tracks: list[CannablissTrack],
    fallback_tracks: list[CannablissTrack],
    limit: int,
    selected_ids: set[str],
    artist_counts: dict[str, int],
    max_tracks_per_artist: int,
    score_kind: str,
    listening_signals: ListeningSignals,
    now: datetime,
) -> list[CannablissTrack]:
    chosen = _select_scored(
        primary_tracks,
        limit,
        selected_ids,
        artist_counts,
        max_tracks_per_artist=max_tracks_per_artist,
        score_kind=score_kind,
        listening_signals=listening_signals,
        now=now,
    )
    if len(chosen) >= limit:
        return chosen
    chosen.extend(
        _select_scored(
            fallback_tracks,
            limit - len(chosen),
            selected_ids,
            artist_counts,
            max_tracks_per_artist=max_tracks_per_artist,
            score_kind=score_kind,
            listening_signals=listening_signals,
            now=now,
        )
    )
    return chosen


def _top_ranked(
    tracks: list[CannablissTrack],
    limit: int,
    score_kind: str,
    now: datetime,
    listening_signals: ListeningSignals = ListeningSignals(),
) -> list[CannablissTrack]:
    scored = sorted(
        tracks,
        key=lambda track: (
            _score_track(
                track,
                score_kind=score_kind,
                listening_signals=listening_signals,
                now=now,
            ),
            track.added_at,
            track.name.lower(),
            track.uri,
        ),
        reverse=True,
    )
    return scored[:limit]


def _ordered_unique(tracks: list[CannablissTrack]) -> list[CannablissTrack]:
    seen: set[str] = set()
    out: list[CannablissTrack] = []
    for track in tracks:
        if track.uri in seen:
            continue
        seen.add(track.uri)
        out.append(track)
    return out


def _front_queue_candidates(
    tracks: list[CannablissTrack],
    *,
    now: datetime,
) -> list[CannablissTrack]:
    queued: list[CannablissTrack] = []
    for track in tracks:
        if "hall" in track.source_tags:
            continue
        if not ("master" in track.source_tags or any(tag.startswith("feeder:") for tag in track.source_tags)):
            continue
        added = _parse_datetime(track.added_at)
        if added is None:
            continue
        age_days = max(0.0, (now - added).total_seconds() / 86400)
        if age_days <= MAJOR_FRONT_QUEUE_DAYS:
            queued.append(track)
    return queued


def _prune_tail_candidates(
    tracks: list[CannablissTrack],
    *,
    limit: int,
    listening_signals: ListeningSignals,
    now: datetime,
) -> list[CannablissTrack]:
    """Trim the lower-value tail first while preserving stronger anchors."""
    if limit <= 0:
        return []
    if len(tracks) <= limit:
        return _top_ranked(tracks, len(tracks), "library", now, listening_signals)

    kept = sorted(
        tracks,
        key=lambda track: (
            _tail_strength(track, listening_signals=listening_signals, now=now),
            _score_track(track, score_kind="library", listening_signals=listening_signals, now=now),
            -((track.current_position or 10**9)),
            track.added_at,
            track.uri,
        ),
        reverse=True,
    )[:limit]
    return _top_ranked(kept, limit, "library", now, listening_signals)


def _tail_strength(
    track: CannablissTrack,
    *,
    listening_signals: ListeningSignals,
    now: datetime,
) -> float:
    score = _score_track(track, score_kind="library", listening_signals=listening_signals, now=now)
    source_confidence = 0.0
    if "master" in track.source_tags:
        source_confidence += 0.05
    if any(tag.startswith("feeder:") for tag in track.source_tags):
        source_confidence += 0.04
    if "hall" in track.source_tags:
        source_confidence -= 0.02

    incumbency = 0.0
    if track.current_position is not None:
        if track.current_position <= 50:
            incumbency = 0.18
        elif track.current_position <= 100:
            incumbency = 0.12
        else:
            incumbency = 0.05

    bottom_pressure = 0.0
    if track.current_position is not None and track.current_position > 100:
        bottom_pressure = -0.12
    elif track.current_position is not None and track.current_position > 75:
        bottom_pressure = -0.05

    return score + source_confidence + incumbency + bottom_pressure


def _score_track(
    track: CannablissTrack,
    *,
    score_kind: str,
    listening_signals: ListeningSignals,
    now: datetime,
) -> float:
    added_score = _recency_score(track.added_at, now)
    release_bias = _release_bias(track.release_date, now)
    popularity_bonus = ((track.popularity or 0) / 100.0) * 0.04

    feeder_bonus = 0.12 if any(tag.startswith("feeder:") for tag in track.source_tags) else 0.0
    master_bonus = 0.05 if "master" in track.source_tags else 0.0
    hall_bonus = -0.03 if "hall" in track.source_tags else 0.0

    incumbency = 0.0
    if track.current_position is not None:
        if track.current_position <= 10:
            incumbency = 0.25
        elif track.current_position <= 40:
            incumbency = 0.18
        elif track.current_position <= 80:
            incumbency = 0.10
        else:
            incumbency = 0.05

    tid = track_id(track.uri)
    top_listen_bonus = (
        listening_signals.top_tracks_boost if tid in listening_signals.top_track_ids else 0.0
    )
    recent_listen_bonus = (
        listening_signals.recently_played_boost
        if tid in listening_signals.recently_played_ids
        else 0.0
    )

    if score_kind == "premium":
        return (
            added_score * 0.9
            + release_bias
            + feeder_bonus
            + popularity_bonus
            + incumbency
            + master_bonus
            + hall_bonus
            + top_listen_bonus
            + recent_listen_bonus * 0.8
        )
    if score_kind == "new":
        return (
            added_score
            + release_bias
            + feeder_bonus
            + popularity_bonus
            + master_bonus
            + hall_bonus
            + top_listen_bonus * 0.6
            + recent_listen_bonus * 0.7
        )
    if score_kind == "discovery":
        return (
            added_score * 0.95
            + feeder_bonus
            + release_bias
            + hall_bonus
            + top_listen_bonus * 0.35
            + recent_listen_bonus * 0.45
        )
    if score_kind == "stabilizer":
        return (
            incumbency
            + 0.5 * added_score
            + popularity_bonus
            + 0.5 * feeder_bonus
            + hall_bonus
            + top_listen_bonus * 0.35
            + recent_listen_bonus * 0.2
        )
    return (
        0.7 * added_score
        + 0.8 * incumbency
        + 0.3 * feeder_bonus
        + popularity_bonus
        + hall_bonus
        + top_listen_bonus * 0.2
        + recent_listen_bonus * 0.15
    )


def _recency_score(added_at: str, now: datetime) -> float:
    parsed = _parse_datetime(added_at)
    if parsed is None:
        return 0.0
    age_days = max(0.0, (now - parsed).total_seconds() / 86400)
    if age_days <= 7:
        return 1.0
    if age_days <= 30:
        return 0.85
    if age_days <= 90:
        return 0.65
    if age_days <= 180:
        return 0.45
    if age_days <= 365:
        return 0.25
    return 0.1


def _release_bias(release_date: str, now: datetime) -> float:
    parsed = _parse_release_date(release_date)
    if parsed is None:
        return 0.0
    age_days = max(0, (now.date() - parsed).days)
    if age_days <= 30:
        return 0.12
    if age_days <= 180:
        return 0.08
    if age_days <= 365:
        return 0.05
    if age_days <= 3650:
        return 0.02
    return 0.0


def _interleave_tracks(
    left: list[CannablissTrack],
    right: list[CannablissTrack],
    limit: int,
) -> list[CannablissTrack]:
    out: list[CannablissTrack] = []
    i = j = 0
    while len(out) < limit and (i < len(left) or j < len(right)):
        if i < len(left):
            out.append(left[i])
            i += 1
            if len(out) >= limit:
                break
        if j < len(right):
            out.append(right[j])
            j += 1
    return out[:limit]


def track_id(uri: str) -> str:
    if ":" in uri:
        return uri.rsplit(":", 1)[-1]
    return uri


def _has_listening_signal(track: CannablissTrack, signals: ListeningSignals) -> bool:
    tid = track_id(track.uri)
    return tid in signals.top_track_ids or tid in signals.recently_played_ids


def _song_key(track: CannablissTrack) -> str:
    return f"{_primary_artist(track.artists)}::{_normalize_title(track.name)}"


def _normalize_title(name: str) -> str:
    lowered = name.lower()
    for sep in (" - ", " (", " ["):
        if sep in lowered:
            lowered = lowered.split(sep, 1)[0]
    normalized = "".join(ch for ch in lowered if ch.isalnum() or ch.isspace())
    return " ".join(normalized.split())


def _variant_rank(track: CannablissTrack) -> tuple[float, int, int, int]:
    return (
        1.0 if track.current_position is not None else 0.0,
        1 if "master" in track.source_tags else 0,
        track.popularity or 0,
        int(_parse_datetime(track.added_at).timestamp()) if _parse_datetime(track.added_at) else 0,
    )


def _primary_artist(artists: str) -> str:
    primary = artists.split(",")[0].strip().lower()
    return primary or "unknown"


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_release_date(value: str) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None
