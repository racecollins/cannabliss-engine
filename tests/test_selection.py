"""Unit tests for selection logic."""

import pytest
from src.selection import Track, parse_tracks, deduplicate, select_recent, select_random, select_tracks


# ── Fixtures ─────────────────────────────────────────────────────────

def _item(uri: str, name: str = "Song", artist: str = "Artist",
          added_at: str = "2025-01-01T00:00:00Z", track_type: str = "track",
          is_local: bool = False) -> dict:
    """Helper to build a raw Spotify playlist item."""
    return {
        "added_at": added_at,
        "track": {
            "uri": uri,
            "name": name,
            "artists": [{"name": artist}],
            "type": track_type,
            "is_local": is_local,
        },
    }


def _item_v2(uri: str, name: str = "Song", artist: str = "Artist",
             added_at: str = "2025-01-01T00:00:00Z", track_type: str = "track",
             is_local: bool = False) -> dict:
    """Helper to build a `/items`-style payload where content is in `item`."""
    return {
        "added_at": added_at,
        "is_local": is_local,
        "item": {
            "uri": uri,
            "name": name,
            "artists": [{"name": artist}],
            "type": track_type,
            "is_local": is_local,
        },
    }


# ── parse_tracks ─────────────────────────────────────────────────────

class TestParseTracks:
    def test_basic(self):
        items = [_item("spotify:track:aaa", "Song A", "Art A")]
        result = parse_tracks(items)
        assert len(result) == 1
        assert result[0].uri == "spotify:track:aaa"
        assert result[0].name == "Song A"
        assert result[0].artists == "Art A"

    def test_filters_episodes(self):
        items = [
            _item("spotify:track:aaa", track_type="track"),
            _item("spotify:episode:bbb", track_type="episode"),
        ]
        result = parse_tracks(items)
        assert len(result) == 1

    def test_filters_local(self):
        items = [_item("spotify:local:xxx", is_local=True)]
        result = parse_tracks(items)
        assert len(result) == 0

    def test_filters_null_track(self):
        items = [{"added_at": "2025-01-01T00:00:00Z", "track": None}]
        result = parse_tracks(items)
        assert len(result) == 0

    def test_filters_missing_uri(self):
        item = _item("spotify:track:aaa")
        del item["track"]["uri"]
        result = parse_tracks([item])
        assert len(result) == 0

    def test_parses_items_endpoint_shape(self):
        items = [_item_v2("spotify:track:xyz", "Song X", "Art X")]
        result = parse_tracks(items)
        assert len(result) == 1
        assert result[0].uri == "spotify:track:xyz"


# ── deduplicate ──────────────────────────────────────────────────────

class TestDeduplicate:
    def test_no_dupes(self):
        tracks = [
            Track("spotify:track:a", "A", "Art", "2025-01-01T00:00:00Z"),
            Track("spotify:track:b", "B", "Art", "2025-01-02T00:00:00Z"),
        ]
        result = deduplicate(tracks)
        assert len(result) == 2

    def test_keeps_most_recent(self):
        tracks = [
            Track("spotify:track:a", "A-old", "Art", "2025-01-01T00:00:00Z"),
            Track("spotify:track:a", "A-new", "Art", "2025-06-01T00:00:00Z"),
        ]
        result = deduplicate(tracks)
        assert len(result) == 1
        assert result[0].name == "A-new"
        assert result[0].added_at == "2025-06-01T00:00:00Z"

    def test_multiple_dupes(self):
        tracks = [
            Track("spotify:track:a", "A1", "Art", "2025-01-01T00:00:00Z"),
            Track("spotify:track:b", "B1", "Art", "2025-01-02T00:00:00Z"),
            Track("spotify:track:a", "A2", "Art", "2025-03-01T00:00:00Z"),
            Track("spotify:track:b", "B2", "Art", "2025-01-01T00:00:00Z"),
        ]
        result = deduplicate(tracks)
        assert len(result) == 2
        by_uri = {t.uri: t for t in result}
        assert by_uri["spotify:track:a"].name == "A2"
        assert by_uri["spotify:track:b"].name == "B1"


# ── select_recent ────────────────────────────────────────────────────

class TestSelectRecent:
    def test_picks_most_recent(self):
        tracks = [
            Track("spotify:track:a", "A", "Art", "2025-01-01T00:00:00Z"),
            Track("spotify:track:b", "B", "Art", "2025-06-01T00:00:00Z"),
            Track("spotify:track:c", "C", "Art", "2025-03-01T00:00:00Z"),
        ]
        result = select_recent(tracks, 2)
        assert [t.uri for t in result] == ["spotify:track:b", "spotify:track:c"]

    def test_fewer_than_count(self):
        tracks = [Track("spotify:track:a", "A", "Art", "2025-01-01T00:00:00Z")]
        result = select_recent(tracks, 5)
        assert len(result) == 1


# ── select_random ────────────────────────────────────────────────────

class TestSelectRandom:
    def test_correct_count(self):
        tracks = [Track(f"spotify:track:{i}", f"S{i}", "Art", "") for i in range(200)]
        result = select_random(tracks, 100, seed=42)
        assert len(result) == 100

    def test_no_duplicates(self):
        tracks = [Track(f"spotify:track:{i}", f"S{i}", "Art", "") for i in range(200)]
        result = select_random(tracks, 100, seed=42)
        uris = [t.uri for t in result]
        assert len(set(uris)) == 100

    def test_deterministic_with_seed(self):
        tracks = [Track(f"spotify:track:{i}", f"S{i}", "Art", "") for i in range(200)]
        r1 = select_random(tracks, 50, seed=123)
        r2 = select_random(tracks, 50, seed=123)
        assert [t.uri for t in r1] == [t.uri for t in r2]

    def test_different_seeds_differ(self):
        tracks = [Track(f"spotify:track:{i}", f"S{i}", "Art", "") for i in range(200)]
        r1 = select_random(tracks, 50, seed=1)
        r2 = select_random(tracks, 50, seed=2)
        assert [t.uri for t in r1] != [t.uri for t in r2]

    def test_fewer_than_count(self):
        tracks = [Track(f"spotify:track:{i}", f"S{i}", "Art", "") for i in range(5)]
        result = select_random(tracks, 100, seed=42)
        assert len(result) == 5


# ── select_tracks (integration) ─────────────────────────────────────

class TestSelectTracks:
    def test_full_pipeline_random(self):
        items = [_item(f"spotify:track:{i}", f"Song {i}", "Art", f"2025-01-{i+1:02d}T00:00:00Z")
                 for i in range(150)]
        # Add a duplicate
        items.append(_item("spotify:track:0", "Song 0 dup", "Art", "2025-06-01T00:00:00Z"))
        # Add an episode
        items.append(_item("spotify:episode:ep1", track_type="episode"))

        result = select_tracks(items, "random", 100, seed=42)
        assert len(result) == 100
        uris = [t.uri for t in result]
        assert len(set(uris)) == 100

    def test_full_pipeline_recent(self):
        items = [_item(f"spotify:track:{i}", f"Song {i}", "Art", f"2025-{(i % 12) + 1:02d}-01T00:00:00Z")
                 for i in range(150)]
        result = select_tracks(items, "recent", 10)
        assert len(result) == 10
        # Should be sorted by most recent
        dates = [t.added_at for t in result]
        assert dates == sorted(dates, reverse=True)
