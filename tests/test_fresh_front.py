"""Tests for the fresh-front builder."""

from datetime import datetime, timezone

from src.cannabliss import CannablissTrack, ListeningSignals, _build_fresh_front

NOW = datetime(2026, 6, 19, tzinfo=timezone.utc)


def _t(i, *, added_at="2026-06-10T00:00:00Z", artist=None, current_position=None):
    return CannablissTrack(
        uri=f"spotify:track:{i}",
        name=f"Song {i}",
        artists=artist or f"Artist {i}",
        added_at=added_at,
        source_tags={"current"},
        current_position=current_position,
        popularity=50,
        release_date="2026-06-01",
    )


def test_weekly_adds_ordered_newest_first():
    adds = [
        _t(1, added_at="2026-06-15T00:00:00Z"),
        _t(2, added_at="2026-06-18T00:00:00Z"),
        _t(3, added_at="2026-06-12T00:00:00Z"),
    ]
    front = _build_fresh_front(
        adds, weekly_add_ids={t.uri for t in adds}, size=15,
        max_per_artist=2, signals=ListeningSignals(), now=NOW,
    )
    assert [t.uri for t in front] == ["spotify:track:2", "spotify:track:1", "spotify:track:3"]


def test_hot_pick_incumbent_lands_in_top_5_over_fresher_adds():
    adds = [_t(10 + i, added_at=f"2026-06-1{i}T00:00:00Z") for i in range(8)]
    hot_incumbent = _t(999, added_at="2026-01-01T00:00:00Z", current_position=40)
    signals = ListeningSignals(top_track_ids=frozenset({"999"}), top_tracks_boost=0.4)
    front = _build_fresh_front(
        adds + [hot_incumbent], weekly_add_ids={t.uri for t in adds},
        size=15, max_per_artist=2, signals=signals, now=NOW,
    )
    assert hot_incumbent.uri in {t.uri for t in front[:5]}


def test_artist_cap_limits_front_to_two_per_artist():
    binge = [_t(i, artist="Binge Artist", added_at=f"2026-06-1{i}T00:00:00Z") for i in range(7)]
    others = [_t(100 + i, added_at="2026-06-05T00:00:00Z") for i in range(15)]
    front = _build_fresh_front(
        binge + others, weekly_add_ids={t.uri for t in binge},
        size=15, max_per_artist=2, signals=ListeningSignals(), now=NOW,
    )
    binge_in_front = [t for t in front if t.artists == "Binge Artist"]
    assert len(binge_in_front) == 2
    assert len(front) == 15


def test_rolling_fill_tops_up_when_few_weekly_adds():
    adds = [_t(i, added_at="2026-06-18T00:00:00Z") for i in range(8)]
    fill = [_t(200 + i, added_at="2026-06-09T00:00:00Z") for i in range(20)]
    front = _build_fresh_front(
        adds + fill, weekly_add_ids={t.uri for t in adds},
        size=15, max_per_artist=2, signals=ListeningSignals(), now=NOW,
    )
    assert len(front) == 15
    # All 8 weekly adds rank above fill (newer + weekly-add tier).
    assert {t.uri for t in adds} <= {t.uri for t in front[:8]}
