"""Unit tests for selection logic."""

from datetime import datetime, timezone
import pytest
from src.selection import (
    Track,
    deduplicate,
    enforce_artist_cap,
    filter_by_history,
    parse_tracks,
    select_random,
    select_recent,
    select_tracks,
    select_tracks_from_tracks,
    weighted_sample,
)


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
        result, _ = select_random(tracks, 100, seed=42)
        assert len(result) == 100

    def test_no_duplicates(self):
        tracks = [Track(f"spotify:track:{i}", f"S{i}", "Art", "") for i in range(200)]
        result, _ = select_random(tracks, 100, seed=42)
        uris = [t.uri for t in result]
        assert len(set(uris)) == 100

    def test_deterministic_with_seed(self):
        tracks = [Track(f"spotify:track:{i}", f"S{i}", "Art", "") for i in range(200)]
        r1, _ = select_random(tracks, 50, seed=123)
        r2, _ = select_random(tracks, 50, seed=123)
        assert [t.uri for t in r1] == [t.uri for t in r2]

    def test_different_seeds_differ(self):
        tracks = [Track(f"spotify:track:{i}", f"S{i}", "Art", "") for i in range(200)]
        r1, _ = select_random(tracks, 50, seed=1)
        r2, _ = select_random(tracks, 50, seed=2)
        assert [t.uri for t in r1] != [t.uri for t in r2]

    def test_fewer_than_count(self):
        tracks = [Track(f"spotify:track:{i}", f"S{i}", "Art", "") for i in range(5)]
        result, _ = select_random(tracks, 100, seed=42)
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


class TestHistoryFiltering:
    def test_excludes_recent_history_runs(self):
        tracks = [
            Track("spotify:track:a", "A", "Art", "2025-01-01T00:00:00Z"),
            Track("spotify:track:b", "B", "Art", "2025-01-02T00:00:00Z"),
            Track("spotify:track:c", "C", "Art", "2025-01-03T00:00:00Z"),
        ]
        history = [
            {"track_ids": ["z"]},
            {"track_ids": ["b"]},
        ]
        result = filter_by_history(tracks, history, history_weeks=1)
        assert [t.uri for t in result] == ["spotify:track:a", "spotify:track:c"]

    def test_relaxes_history_when_pool_too_small(self):
        tracks = [Track(f"spotify:track:{i}", f"S{i}", "Art", "2025-01-01T00:00:00Z") for i in range(5)]
        history = [{"track_ids": [str(i) for i in range(5)]}]
        selected, meta = select_tracks_from_tracks(
            tracks,
            mode="random",
            count=3,
            seed=1,
            history_runs=history,
            history_weeks=6,
        )
        assert len(selected) == 3
        assert meta["used_history_filter"] is False


class TestArtistCap:
    def test_enforces_cap(self):
        tracks = [
            Track("spotify:track:1", "S1", "A, X", "2025-01-03T00:00:00Z"),
            Track("spotify:track:2", "S2", "A, Y", "2025-01-02T00:00:00Z"),
            Track("spotify:track:3", "S3", "A, Z", "2025-01-01T00:00:00Z"),
            Track("spotify:track:4", "S4", "B, X", "2025-01-04T00:00:00Z"),
            Track("spotify:track:5", "S5", "C, X", "2025-01-05T00:00:00Z"),
        ]
        selected, cap_used = enforce_artist_cap(tracks, count=4, max_tracks_per_artist=1)
        assert cap_used == 2
        assert len(selected) == 4


class TestWeightedSample:
    def test_weighted_sampler_deterministic_with_seed(self):
        tracks = [
            Track(f"spotify:track:{i}", f"S{i}", "Art", f"2025-01-{(i % 28) + 1:02d}T00:00:00Z")
            for i in range(60)
        ]
        now = datetime(2025, 2, 1, tzinfo=timezone.utc)
        r1 = weighted_sample(tracks, 20, seed=7, now=now)
        r2 = weighted_sample(tracks, 20, seed=7, now=now)
        assert [t.uri for t in r1] == [t.uri for t in r2]

    def test_newer_tracks_are_preferred_in_aggregate(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        recent = [Track(f"spotify:track:r{i}", f"R{i}", "AR", "2025-12-20T00:00:00Z") for i in range(25)]
        mid = [Track(f"spotify:track:m{i}", f"M{i}", "AM", "2025-09-01T00:00:00Z") for i in range(25)]
        old = [Track(f"spotify:track:o{i}", f"O{i}", "AO", "2024-01-01T00:00:00Z") for i in range(25)]
        tracks = recent + mid + old

        picked_recent = 0
        picked_old = 0
        for seed in range(30):
            result = weighted_sample(tracks, 30, seed=seed, now=now)
            uris = {t.uri for t in result}
            picked_recent += sum(1 for t in recent if t.uri in uris)
            picked_old += sum(1 for t in old if t.uri in uris)

        assert picked_recent > picked_old
