"""Tests for fresh-front / body scoring helpers."""

from datetime import datetime, timezone

from src.cannabliss import (
    CannablissTrack,
    ListeningSignals,
    _body_score,
    _body_sort_key,
    _front_score,
    _front_sort_key,
    _is_hot_pick,
)

NOW = datetime(2026, 6, 19, tzinfo=timezone.utc)


def _t(i, *, added_at="2026-06-18T00:00:00Z", popularity=50, source_tags=None,
       current_position=None):
    return CannablissTrack(
        uri=f"spotify:track:{i}",
        name=f"Song {i}",
        artists=f"Artist {i}",
        added_at=added_at,
        source_tags=source_tags or {"master"},
        current_position=current_position,
        popularity=popularity,
        release_date="2026-06-01",
    )


def test_is_hot_pick_checks_top_tracks_only():
    signals = ListeningSignals(top_track_ids=frozenset({"1"}), recently_played_ids=frozenset({"2"}))
    assert _is_hot_pick(_t(1), signals) is True
    assert _is_hot_pick(_t(2), signals) is False


def test_front_score_adds_full_listening_boosts():
    signals = ListeningSignals(
        top_track_ids=frozenset({"1"}), top_tracks_boost=0.3,
        recently_played_ids=frozenset({"1"}), recently_played_boost=0.2,
    )
    base = _front_score(_t(9), ListeningSignals(), NOW)
    boosted = _front_score(_t(1), signals, NOW)
    assert boosted == base + 0.3 + 0.2


def test_body_score_penalizes_hall_and_uses_half_listening():
    signals = ListeningSignals(top_track_ids=frozenset({"1"}), top_tracks_boost=0.4)
    plain = _body_score(_t(9), ListeningSignals(), NOW)
    boosted = _body_score(_t(1), signals, NOW)
    assert boosted == plain + 0.2  # half of 0.4
    hall = _body_score(_t(2, source_tags={"hall"}), ListeningSignals(), NOW)
    assert hall < plain


def test_body_sort_key_orders_lower_position_first_on_ties():
    # Same score inputs; stability tiebreaker prefers the lower current_position.
    a = _t(1, current_position=5)
    b = _t(2, current_position=80)
    key_a = _body_sort_key(a, ListeningSignals(), NOW)
    key_b = _body_sort_key(b, ListeningSignals(), NOW)
    assert key_a > key_b  # reverse=True sort puts a (pos 5) ahead of b (pos 80)


def test_front_sort_key_tiers_hot_above_weekly_above_fresh():
    # The tier flags dominate the key: a hot pick outranks a weekly add, which
    # outranks a merely-fresh track — even when the fresh track is the newest.
    signals = ListeningSignals(top_track_ids=frozenset({"1"}), top_tracks_boost=0.4)
    hot = _t(1, added_at="2026-06-01T00:00:00Z")     # hot pick, oldest
    weekly = _t(2, added_at="2026-06-05T00:00:00Z")  # weekly add
    fresh = _t(3, added_at="2026-06-19T00:00:00Z")   # newest, but neither hot nor weekly
    weekly_add_ids = {"spotify:track:2"}
    k_hot = _front_sort_key(hot, signals, NOW, weekly_add_ids)
    k_weekly = _front_sort_key(weekly, signals, NOW, weekly_add_ids)
    k_fresh = _front_sort_key(fresh, signals, NOW, weekly_add_ids)
    # reverse=True sort ranks larger keys first: hot > weekly > fresh.
    assert k_hot > k_weekly > k_fresh
