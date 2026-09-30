"""Cannabliss-specific curated playlist builder and state tracking."""

from __future__ import annotations

import copy
import json
import tempfile
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


DEFAULT_FRESH_FRONT_SIZE = 15
DEFAULT_FRESH_FRONT_MAX_PER_ARTIST = 2
DEFAULT_REMOVAL_COOLDOWN_DAYS = 7
HALL_BODY_PENALTY = 0.05


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
    removed_uris: list[str] = field(default_factory=list)
    rotation_state: dict = field(default_factory=dict)
    protected_uris: list[str] = field(default_factory=list)
    reasons: dict[str, str] = field(default_factory=dict)
    bootstrap: bool = False


@dataclass(frozen=True)
class ListeningSignals:
    top_track_ids: frozenset[str] = frozenset()
    recently_played_ids: frozenset[str] = frozenset()
    top_tracks_boost: float = 0.35
    recently_played_boost: float = 0.25
    top_track_ranks: dict[str, int] = field(default_factory=dict)


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
    """Read history without changing it. Corrupt history must never reset silently."""
    if not os.path.exists(path):
        return {"runs": []}
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict) or not isinstance(data.get("runs"), list):
        raise ValueError("Invalid Cannabliss state; restore history before updating Spotify")
    return data


def save_cannabliss_state(payload: dict, path: str = "data/cannabliss_state.json") -> None:
    """Atomically publish a complete state file."""
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".cannabliss-", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def previous_run_track_uris(state: dict) -> set[str]:
    """URIs (`spotify:track:<id>`) of the most recent recorded run, or empty."""
    runs = state.get("runs") or []
    if not runs:
        return set()
    return {f"spotify:track:{tid}" for tid in runs[-1].get("track_ids", []) if tid}


def append_cannabliss_run(
    result: CannablissBuildResult,
    *,
    path: str = "data/cannabliss_state.json",
    now: datetime | None = None,
    cooldown_days: int = DEFAULT_REMOVAL_COOLDOWN_DAYS,
    target_playlist_id: str | None = None,
) -> None:
    stamp = now or datetime.now(timezone.utc)
    payload = load_cannabliss_state(path)
    runs = payload.setdefault("runs", [])
    runs.append(
        {
            "timestamp": stamp.isoformat(),
            "track_ids": [track_id(t.uri) for t in result.ordered_tracks],
            "new_track_count": result.new_track_count,
            "summary": result.summary,
            "zones": {
                zone: [track_id(t.uri) for t in tracks]
                for zone, tracks in result.zones.items()
            },
        }
    )
    payload["cooldown"] = merge_cooldown(
        payload.get("cooldown", []), result.removed_uris, stamp, days=cooldown_days
    )
    payload["rotation"] = result.rotation_state
    payload["schema_version"] = 2
    if target_playlist_id is not None:
        payload["target_playlist_id"] = target_playlist_id
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
    listening_signals: ListeningSignals | None = None,
    previous_track_uris: frozenset[str] | set[str] = frozenset(),
    cooldown_uris: frozenset[str] | set[str] = frozenset(),
    rotation_state: dict | None = None,
    protection_days: int = 14,
    discovery_per_refresh: int = 5,
    removal_cooldown_days: int = DEFAULT_REMOVAL_COOLDOWN_DAYS,
    fresh_front_size: int = DEFAULT_FRESH_FRONT_SIZE,
    fresh_front_max_per_artist: int = DEFAULT_FRESH_FRONT_MAX_PER_ARTIST,
    learn_top_ten: bool = False,
    queue_curator_additions: bool = False,
    curator_queue_per_refresh: int = 10,
    now: datetime | None = None,
) -> CannablissBuildResult:
    """Honor explicit curator picks, then admit bounded discovery and rotate features.

    State is a proposal only: callers persist it after a verified Spotify write.
    A missing baseline conservatively protects the live membership for 14 days.
    """
    if queue_curator_additions:
        from src.curator_queue import build_with_queue
        options = dict(locals())
        options.pop('build_with_queue', None)
        options['now'] = now or datetime.now(timezone.utc)
        return build_with_queue(options)
    current = now or datetime.now(timezone.utc)
    stamp = current.isoformat()
    signals = listening_signals or ListeningSignals()
    state = copy.deepcopy(rotation_state or {})
    history = state.setdefault("tracks", {})
    prev = set(previous_track_uris)
    known_baseline = rotation_state is not None or bool(prev)
    bootstrap = not known_baseline and bool(current_tracks)
    merged = _dedupe_song_variants(
        merge_track_sets([master_tracks, current_tracks, feeder_tracks, hall_tracks])
    )
    live = _ordered_unique(sorted(current_tracks, key=lambda t: t.current_position or 10**9))
    live = [t for t in live if t.uri in merged]
    current_order = [t.uri for t in live]
    from src.preferences import observe_order, feature_top_ten
    preference_events = observe_order(state, current_order, current) if learn_top_ten else []
    current_ids = set(current_order)
    manual_adds = current_ids - prev if known_baseline else set()
    manual_removed = prev - current_ids
    dismissed = set(state.get("dismissed_uris", [])) | manual_removed
    dismissed_keys = set(state.get("dismissed_song_keys", []))
    for uri in manual_removed:
        key = history.get(uri, {}).get("song_key")
        if not key and uri in merged:
            key = _song_key(merged[uri])
        if key:
            dismissed_keys.add(key)
    # Explicit re-adds override a previous rejection, including another release.
    for track in live:
        if track.uri in manual_adds:
            dismissed.discard(track.uri)
            dismissed_keys.discard(_song_key(track))
        meta = history.setdefault(track.uri, {})
        if track.uri in manual_adds or bootstrap:
            meta.update(
                entered_at=stamp,
                curator_added_at=min(_parse_datetime(track.added_at) or current, current).isoformat(),
                protected_until=(current + timedelta(days=protection_days)).isoformat(),
            )
        meta.setdefault("entered_at", min(_parse_datetime(track.added_at) or current, current).isoformat())
        meta.update(song_key=_song_key(track), name=track.name, artists=track.artists)
        # Spotify and feeder timestamps never renew tenure after the first observation.
        merged[track.uri].added_at = meta["entered_at"]

    protected = [merged[uri] for uri in current_order
                 if (_parse_datetime(history[uri].get("protected_until", "")) or current) > current]
    protected.sort(key=lambda t: (
        history[t.uri].get("curator_added_at", ""), -(t.current_position or 10**9)
    ), reverse=True)
    protected_ids = {t.uri for t in protected}
    if len(protected) > target_size:
        raise ValueError(
            f"{len(protected)} protected curator picks exceed the {target_size}-song target. "
            "No songs were discarded; reduce the live selection or increase the target explicitly."
        )

    week = current.strftime("%G-W%V")
    budget = state.get("weekly_budget", {})
    used = int(budget.get("used", 0)) if budget.get("week") == week else 0
    used += len(manual_adds)
    rotate = update_mode == "major" and state.get("last_major_week") != week and not bootstrap
    initial_empty = not known_baseline and not current_ids
    vacancies = max(0, target_size - len(live))
    allowance = max(0, weekly_insertions - used)
    intake = min(allowance, discovery_per_refresh) if rotate else min(allowance, micro_refresh_count, vacancies)
    if bootstrap:
        intake = 0
    if initial_empty:
        intake = target_size
    intake = min(intake, max(0, target_size - len(protected)))

    candidates = [t for uri, t in merged.items()
                  if uri not in current_ids and uri not in dismissed
                  and _song_key(t) not in dismissed_keys and uri not in set(cooldown_uris)
                  and not (
                      (removed := _parse_datetime(history.get(uri, {}).get("retired_at", "")))
                      and current - removed < timedelta(days=removal_cooldown_days)
                  )]
    candidates.sort(key=lambda t: (
        # Prefer candidates not previously featured or in observed listening.
        # This is recorded novelty, never proof that the user has not heard it.
        not history.get(t.uri, {}).get("last_featured_at") if learn_top_ten else False,
        track_id(t.uri) not in (signals.top_track_ids | signals.recently_played_ids)
        if learn_top_ten else False,
        _body_score(t, signals, current), t.added_at, t.uri), reverse=True)
    counts: dict[str, int] = {}
    for track in live:
        artist = _primary_artist(track.artists)
        counts[artist] = counts.get(artist, 0) + 1
    admitted: list[CannablissTrack] = []
    for track in candidates:
        if len(admitted) >= intake:
            break
        artist = _primary_artist(track.artists)
        if counts.get(artist, 0) >= max_tracks_per_artist:
            continue
        admitted.append(track)
        counts[artist] = counts.get(artist, 0) + 1
        meta = history.setdefault(track.uri, {})
        meta.update(entered_at=stamp, song_key=_song_key(track), name=track.name, artists=track.artists)
        # An automated return is not a new curator endorsement.
        meta.pop("protected_until", None)
        meta.pop("curator_added_at", None)

    incumbents = [merged[uri] for uri in current_order if uri not in protected_ids]

    def retention(track):
        entered = _parse_datetime(history[track.uri]["entered_at"]) or current
        # Listening can delay retirement by at most three days, never indefinitely.
        bonus = min(3.0, (signals.top_tracks_boost if _is_hot_pick(track, signals) else 0.0)
                    + (signals.recently_played_boost if track_id(track.uri) in signals.recently_played_ids else 0.0))
        return (entered + timedelta(days=bonus), -(track.current_position or 10**9))

    keep_slots = max(0, target_size - len(protected) - len(admitted))
    retained = sorted(incumbents, key=retention, reverse=True)[:keep_slots]
    retained.sort(key=lambda t: t.current_position or 10**9)
    if rotate or initial_empty:
        front_fill = admitted + sorted(retained, key=lambda t: (
            history[t.uri].get("last_featured_at", ""), t.current_position or 10**9
        ))
    else:
        front_fill = retained + admitted
    front: list[CannablissTrack] = []
    front_counts: dict[str, int] = {}
    for track in protected + front_fill:
        if len(front) >= min(fresh_front_size, target_size):
            break
        artist = _primary_artist(track.artists)
        if front_counts.get(artist, 0) >= fresh_front_max_per_artist:
            continue
        front.append(track)
        front_counts[artist] = front_counts.get(artist, 0) + 1
    front_ids = {t.uri for t in front}
    body = [t for t in protected + retained + admitted if t.uri not in front_ids]
    ordered = front + body
    if learn_top_ten:
        ordered = feature_top_ten(ordered, current_order, state, signals, current,
                                 rotate=rotate or initial_empty)
        front, body = ordered[:10], ordered[10:]
        front_ids = {t.uri for t in front}
    state["verified_order"] = [t.uri for t in ordered]
    ordered_ids = {t.uri for t in ordered}
    removed_uris = sorted((current_ids | prev) - ordered_ids)
    for uri in current_ids - ordered_ids:
        history[uri]["retired_at"] = stamp
    for track in front:
        history[track.uri]["last_featured_at"] = stamp
    state.update(
        version=2, dismissed_uris=sorted(dismissed), dismissed_song_keys=sorted(dismissed_keys),
        weekly_budget={"week": week, "used": used + len(admitted)},
    )
    if rotate or bootstrap or initial_empty:
        state["last_major_week"] = week
    summary = _build_summary(
        ordered=ordered, current_order=current_order, current_ids=current_ids,
        front=front, update_mode=update_mode, weekly_insertions=weekly_insertions,
        micro_refresh_count=micro_refresh_count,
    )
    reasons = {}
    for track in ordered:
        if track.uri in protected_ids:
            reasons[track.uri] = "Curator pick: protected until " + history[track.uri]["protected_until"][:10]
        elif track.uri not in current_ids:
            reasons[track.uri] = "Discovery from Master/feeder pool within the insertion budget"
        elif track.uri in front_ids and rotate:
            reasons[track.uri] = "Featured rotation: giving another incumbent time near the top"
        else:
            reasons[track.uri] = "Retained; preserving body order"
        if learn_top_ten and track.uri in front_ids:
            reasons[track.uri] += "; top 10 considers listening, release freshness and bounded reorder preferences"
    if preference_events:
        summary["preference_edits"] = [f"{len(preference_events)} relative ordering preferences observed"]
    return CannablissBuildResult(
        ordered_tracks=ordered, zones={"fresh_front": front, "body": body}, summary=summary,
        new_track_count=len(admitted), update_mode=update_mode, removed_uris=removed_uris,
        rotation_state=state, protected_uris=sorted(protected_ids), reasons=reasons, bootstrap=bootstrap,
    )


def _select_simple(
    tracks: list[CannablissTrack],
    *,
    limit: int,
    seen: set[str],
    max_per_artist: int,
) -> list[CannablissTrack]:
    """Pick up to `limit` unseen tracks, capping per primary artist."""
    chosen: list[CannablissTrack] = []
    artist_counts: dict[str, int] = {}
    for track in tracks:
        if len(chosen) >= max(0, limit):
            break
        if track.uri in seen:
            continue
        artist = _primary_artist(track.artists)
        if artist_counts.get(artist, 0) >= max_per_artist:
            continue
        seen.add(track.uri)
        artist_counts[artist] = artist_counts.get(artist, 0) + 1
        chosen.append(track)
    return chosen


def _build_summary(
    *,
    ordered: list[CannablissTrack],
    current_order: list[str],
    current_ids: set[str],
    front: list[CannablissTrack],
    update_mode: str,
    weekly_insertions: int,
    micro_refresh_count: int,
) -> dict[str, list[str]]:
    positions_before = {uri: index for index, uri in enumerate(current_order, start=1)}
    positions_after = {track.uri: index for index, track in enumerate(ordered, start=1)}
    front_before = current_order[:len(front)]
    front_after = [track.uri for track in front]

    summary = {
        "update_mode": [update_mode],
        "added": [track_id(t.uri) for t in ordered if t.uri not in current_ids],
        "promoted": [
            track_id(uri) for uri, old in positions_before.items()
            if uri in positions_after and positions_after[uri] < old
        ],
        "held": [
            track_id(uri) for uri, old in positions_before.items()
            if uri in positions_after and positions_after[uri] == old
        ],
        "shifted_down": [
            track_id(uri) for uri, old in positions_before.items()
            if uri in positions_after and positions_after[uri] > old
        ],
        "removed": [track_id(uri) for uri in current_order if uri not in positions_after],
        "fresh_front_added": [
            track_id(uri) for uri in front_after if uri not in set(front_before)
        ],
        "retained": [track_id(uri) for uri in current_order if uri in positions_after],
    }
    total_changed = len(set(summary["added"] + summary["removed"] + summary["promoted"] + summary["shifted_down"]))
    summary["total_changed"] = [str(total_changed)]
    if update_mode == "micro":
        summary["micro_adjustments"] = [str(total_changed)]
    return summary


def _ordered_unique(tracks: list[CannablissTrack]) -> list[CannablissTrack]:
    seen: set[str] = set()
    out: list[CannablissTrack] = []
    for track in tracks:
        if track.uri in seen:
            continue
        seen.add(track.uri)
        out.append(track)
    return out


def _is_hot_pick(track: CannablissTrack, signals: ListeningSignals) -> bool:
    """A song in the playlist that's also in the user's heavy rotation."""
    return track_id(track.uri) in signals.top_track_ids


def _front_score(track: CannablissTrack, signals: ListeningSignals, now: datetime) -> float:
    tid = track_id(track.uri)
    score = _recency_score(track.added_at, now)
    if tid in signals.top_track_ids:
        score += signals.top_tracks_boost
    if tid in signals.recently_played_ids:
        score += signals.recently_played_boost
    return score


def _body_score(track: CannablissTrack, signals: ListeningSignals, now: datetime) -> float:
    tid = track_id(track.uri)
    score = _recency_score(track.added_at, now)
    if tid in signals.top_track_ids:
        score += signals.top_tracks_boost * 0.5
    if tid in signals.recently_played_ids:
        score += signals.recently_played_boost * 0.5
    score += ((track.popularity or 0) / 100.0) * 0.04
    if "hall" in track.source_tags:
        score -= HALL_BODY_PENALTY
    return score


def _front_sort_key(
    track: CannablissTrack,
    signals: ListeningSignals,
    now: datetime,
    weekly_add_ids: set[str],
) -> tuple:
    """Sort key (use reverse=True): curator picks always outrank listening."""
    return (
        1 if track.uri in weekly_add_ids else 0,
        1 if _is_hot_pick(track, signals) else 0,
        _front_score(track, signals, now),
        track.added_at,
        track.name.lower(),
        track.uri,
    )


def _body_sort_key(
    track: CannablissTrack, signals: ListeningSignals, now: datetime
) -> tuple:
    """Sort key (use reverse=True): body score, then stability (lower position first)."""
    return (
        _body_score(track, signals, now),
        -(track.current_position if track.current_position is not None else 10**9),
        track.added_at,
        track.uri,
    )


def _build_body(
    *,
    protected_overflow: list[CannablissTrack],
    candidates: list[CannablissTrack],
    slots: int,
    max_per_artist: int,
    front_tracks: list[CannablissTrack],
    signals: ListeningSignals,
    now: datetime,
) -> list[CannablissTrack]:
    """Body = protected overflow first, then freshness-ordered fill up to `slots`."""
    body: list[CannablissTrack] = []
    selected: set[str] = set()
    artist_counts: dict[str, int] = {}

    for track in front_tracks:
        artist = _primary_artist(track.artists)
        artist_counts[artist] = artist_counts.get(artist, 0) + 1

    # Protected overflow (Race's hand-adds beyond the front) is placed
    # unconditionally and is never trimmed. In the pathological case of more
    # than `target_size` hand-adds in one week this can push the body past
    # `slots` — protection deliberately wins over the size ceiling.
    for track in protected_overflow:
        if track.uri in selected:
            continue
        selected.add(track.uri)
        artist = _primary_artist(track.artists)
        artist_counts[artist] = artist_counts.get(artist, 0) + 1
        body.append(track)

    ordered = sorted(
        _ordered_unique(candidates),
        key=lambda track: _body_sort_key(track, signals, now),
        reverse=True,
    )
    for track in ordered:
        if len(body) >= slots:
            break
        if track.uri in selected:
            continue
        artist = _primary_artist(track.artists)
        if artist_counts.get(artist, 0) >= max_per_artist:
            continue
        selected.add(track.uri)
        artist_counts[artist] = artist_counts.get(artist, 0) + 1
        body.append(track)
    return body


def _build_fresh_front(
    candidates: list[CannablissTrack],
    *,
    weekly_add_ids: set[str],
    size: int,
    max_per_artist: int,
    signals: ListeningSignals,
    now: datetime,
) -> list[CannablissTrack]:
    """The top `size` of the playlist: hot picks, then weekly adds, then fill."""
    ordered = sorted(
        _ordered_unique(candidates),
        key=lambda track: _front_sort_key(track, signals, now, weekly_add_ids),
        reverse=True,
    )
    front: list[CannablissTrack] = []
    artist_counts: dict[str, int] = {}
    for track in ordered:
        if len(front) >= size:
            break
        artist = _primary_artist(track.artists)
        if artist_counts.get(artist, 0) >= max_per_artist:
            continue
        artist_counts[artist] = artist_counts.get(artist, 0) + 1
        front.append(track)
    return front


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


def active_cooldown_uris(
    cooldown_entries: list[dict], now: datetime, *, days: int
) -> set[str]:
    """URIs removed within the cooldown window (`days`) — excluded from re-add."""
    cutoff = now - timedelta(days=days)
    active: set[str] = set()
    for entry in cooldown_entries:
        removed_at = _parse_datetime(entry.get("removed_at", ""))
        uri = entry.get("uri")
        if removed_at is None or not uri:
            continue
        if removed_at >= cutoff:
            active.add(uri)
    return active


def merge_cooldown(
    cooldown_entries: list[dict],
    removed_uris: list[str],
    now: datetime,
    *,
    days: int,
) -> list[dict]:
    """Prune expired entries, then append newly-removed URIs stamped `now`."""
    cutoff = now - timedelta(days=days)
    kept: list[dict] = []
    seen: set[str] = set()
    for entry in cooldown_entries:
        removed_at = _parse_datetime(entry.get("removed_at", ""))
        uri = entry.get("uri")
        if removed_at is None or not uri or removed_at < cutoff:
            continue
        if uri in seen:
            continue
        seen.add(uri)
        kept.append({"uri": uri, "removed_at": entry["removed_at"]})
    stamp = now.isoformat()
    for uri in removed_uris:
        if uri and uri not in seen:
            seen.add(uri)
            kept.append({"uri": uri, "removed_at": stamp})
    return kept


def track_id(uri: str) -> str:
    if ":" in uri:
        return uri.rsplit(":", 1)[-1]
    return uri


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
