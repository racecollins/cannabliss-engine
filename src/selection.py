"""Selection logic: filter, deduplicate, and pick tracks."""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class Track:
    uri: str
    name: str
    artists: str
    added_at: str  # ISO-8601


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


def select_random(tracks: list[Track], count: int, seed: int | None = None) -> list[Track]:
    """Uniformly sample `count` distinct tracks. Deterministic if seed provided."""
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

    unique = deduplicate(tracks)
    if len(unique) < len(tracks):
        print(f"🔁 Deduplicated: {len(tracks)} → {len(unique)} unique tracks")

    if len(unique) < count:
        print(f"⚠️  Only {len(unique)} tracks available (requested {count})")

    if mode == "recent":
        return select_recent(unique, count)
    else:
        return select_random(unique, count, seed)
