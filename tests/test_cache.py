"""Tests for playlist read caching."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.cache import get_cached_playlist_items


class _FakeClient:
    def __init__(self, items):
        self.items = items
        self.calls = 0

    def get_all_playlist_items(self, playlist_id: str):
        self.calls += 1
        return list(self.items)


def _write_cache(path: Path, *, fetched_at: datetime, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "playlist_id": "playlist123",
        "fetched_at": fetched_at.isoformat(),
        "items": items,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_uses_fresh_cache(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_path = cache_dir / "playlist123.json"
    cached_items = [{"id": 1}]
    _write_cache(
        cache_path,
        fetched_at=datetime.now(timezone.utc) - timedelta(hours=1),
        items=cached_items,
    )

    client = _FakeClient(items=[{"id": 2}])
    out = get_cached_playlist_items(
        client,
        "playlist123",
        cache_dir=str(cache_dir),
        ttl_hours=12,
    )

    assert out == cached_items
    assert client.calls == 0


def test_refreshes_when_cache_missing_or_stale(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_path = cache_dir / "playlist123.json"
    _write_cache(
        cache_path,
        fetched_at=datetime.now(timezone.utc) - timedelta(hours=24),
        items=[{"id": 1}],
    )

    client = _FakeClient(items=[{"id": 2}])
    out = get_cached_playlist_items(
        client,
        "playlist123",
        cache_dir=str(cache_dir),
        ttl_hours=12,
    )

    assert out == [{"id": 2}]
    assert client.calls == 1


def test_force_refresh_bypasses_cache(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_path = cache_dir / "playlist123.json"
    _write_cache(
        cache_path,
        fetched_at=datetime.now(timezone.utc),
        items=[{"id": 1}],
    )

    client = _FakeClient(items=[{"id": 3}])
    out = get_cached_playlist_items(
        client,
        "playlist123",
        cache_dir=str(cache_dir),
        ttl_hours=12,
        force_refresh=True,
    )

    assert out == [{"id": 3}]
    assert client.calls == 1
