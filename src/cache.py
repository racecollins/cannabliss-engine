"""Local cache helpers for Spotify playlist reads."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.spotify_client import SpotifyClient


def get_cached_playlist_items(
    client: SpotifyClient,
    playlist_id: str,
    *,
    cache_dir: str,
    ttl_hours: int,
    force_refresh: bool = False,
) -> list[dict]:
    """Read playlist items from cache when fresh, otherwise fetch and refresh."""
    cache_path = _cache_path(cache_dir, playlist_id)
    if not force_refresh:
        cached = _read_cache(cache_path, ttl_hours)
        if cached is not None:
            print(f"💾 Using cached playlist {playlist_id} ({len(cached)} items)")
            return cached

    items = client.get_all_playlist_items(playlist_id)
    _write_cache(cache_path, playlist_id, items)
    return items


def _cache_path(cache_dir: str, playlist_id: str) -> Path:
    root = Path(cache_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{playlist_id}.json"


def _read_cache(path: Path, ttl_hours: int) -> list[dict] | None:
    if ttl_hours <= 0 or not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    fetched_at_raw = payload.get("fetched_at")
    items = payload.get("items")
    if not fetched_at_raw or not isinstance(items, list):
        return None

    try:
        fetched_at = datetime.fromisoformat(fetched_at_raw)
    except ValueError:
        return None

    age = datetime.now(timezone.utc) - fetched_at
    if age > timedelta(hours=ttl_hours):
        return None
    return items


def _write_cache(path: Path, playlist_id: str, items: list[dict]) -> None:
    payload = {
        "playlist_id": playlist_id,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
