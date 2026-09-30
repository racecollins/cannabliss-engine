"""User-level scenarios across multiple Spotify refreshes."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from src.cannabliss import CannablissTrack, ListeningSignals, build_cannabliss_playlist

NOW = datetime(2026, 9, 25, tzinfo=timezone.utc)


def track(i, *, date="2026-01-01T00:00:00Z", pos=None, artist=None):
    return CannablissTrack(f"spotify:track:{i}", f"Song {i}", artist or f"Artist {i}",
                          date, {"current"} if pos else {"master"}, pos)


def current_list(n=100):
    return [track(i, pos=i + 1) for i in range(n)]


def build(current, master=(), *, prior=None, state=None, now=NOW, **kwargs):
    return build_cannabliss_playlist(
        current_tracks=current, master_tracks=list(master), feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25,
        previous_track_uris={t.uri for t in (current if prior is None else prior)},
        rotation_state=state, now=now, **kwargs,
    )


def spotify_rewrite(result, now):
    """Spotify rewrites added_at, but that must not reset tenure or protection."""
    return [replace(t, added_at=now.isoformat(), current_position=i + 1)
            for i, t in enumerate(result.ordered_tracks)]


def test_explicit_pick_beats_fifteen_heavy_rotation_favorites():
    current = current_list()
    pick = track("pick", pos=101, date=NOW.isoformat())
    result = build(current + [pick], prior=current, listening_signals=ListeningSignals(
        top_track_ids=frozenset(str(i) for i in range(15))))
    assert result.ordered_tracks[0].uri == pick.uri
    assert len(result.ordered_tracks) == 100


def test_protection_survives_refreshes_but_expires_after_fourteen_days():
    current = current_list()
    pick = track("pick", pos=101, date=NOW.isoformat())
    first = build(current + [pick], prior=current)
    protected_until = first.rotation_state["tracks"][pick.uri]["protected_until"]
    for days in (3, 7, 13, 15):
        current = spotify_rewrite(first, NOW + timedelta(days=days))
        first = build(current, [track(f"new{days}-{i}") for i in range(50)],
                      state=first.rotation_state, now=NOW + timedelta(days=days))
        assert first.rotation_state["tracks"][pick.uri]["protected_until"] == protected_until
        if days < 14:
            assert pick.uri in {t.uri for t in first.ordered_tracks}
            assert pick.uri in first.protected_uris
        else:
            assert pick.uri not in first.protected_uris


def test_source_timestamp_cannot_renew_incumbent_tenure():
    current = current_list()
    first = build(current)
    later = NOW + timedelta(days=7)
    rewritten = spotify_rewrite(first, later)
    result = build(rewritten, [replace(t, added_at=later.isoformat()) for t in rewritten],
                   state=first.rotation_state, now=later)
    uri = current[0].uri
    assert result.rotation_state["tracks"][uri]["entered_at"] == first.rotation_state["tracks"][uri]["entered_at"]


def test_removed_pick_stays_out_beyond_cooldown_until_manually_readded():
    current = current_list()
    first = build(current)
    deleted = current[0]
    remaining = [t for t in spotify_rewrite(first, NOW) if t.uri != deleted.uri]
    second = build(remaining, [deleted], prior=first.ordered_tracks, state=first.rotation_state)
    assert deleted.uri not in {t.uri for t in second.ordered_tracks}
    third = build(spotify_rewrite(second, NOW), [deleted], state=second.rotation_state,
                  now=NOW + timedelta(days=21))
    assert deleted.uri not in {t.uri for t in third.ordered_tracks}
    readded = replace(deleted, added_at=(NOW + timedelta(days=22)).isoformat(), current_position=100)
    fourth = build(spotify_rewrite(third, NOW) + [readded], [deleted], prior=third.ordered_tracks,
                   state=third.rotation_state, now=NOW + timedelta(days=22))
    assert fourth.ordered_tracks[0].uri == deleted.uri


def test_new_master_candidates_cannot_replace_entire_playlist():
    result = build(current_list(), [track(f"new{i}", date=NOW.isoformat()) for i in range(200)])
    assert result.new_track_count <= 5
    assert len(result.ordered_tracks) == 100
    assert len(result.summary["removed"]) == result.new_track_count


def test_micro_preserves_membership_when_full_and_trims_for_manual_add():
    current = current_list()
    pool = [track(f"new{i}", date=NOW.isoformat()) for i in range(20)]
    result = build(current, pool, update_mode="micro")
    assert {t.uri for t in result.ordered_tracks} == {t.uri for t in current}
    pick = track("pick", pos=101, date=NOW.isoformat())
    result = build(current + [pick], pool, prior=current, update_mode="micro")
    assert result.ordered_tracks[0].uri == pick.uri
    assert len(result.ordered_tracks) == 100


def test_top_changes_next_week_even_without_new_candidates_or_listening_changes():
    current = current_list()
    signals = ListeningSignals(top_track_ids=frozenset(str(i) for i in range(15)))
    first = build(current, listening_signals=signals)
    second = build(spotify_rewrite(first, NOW), state=first.rotation_state,
                   now=NOW + timedelta(days=7), listening_signals=signals)
    assert set(t.uri for t in first.ordered_tracks[:15]).isdisjoint(
        t.uri for t in second.ordered_tracks[:15])


def test_repeated_major_in_same_week_does_not_rotate_again():
    pool = [track(f"new{i}", date=NOW.isoformat()) for i in range(50)]
    first = build(current_list(), pool)
    second = build(spotify_rewrite(first, NOW), pool, state=first.rotation_state,
                   now=NOW + timedelta(hours=1))
    assert [t.uri for t in second.ordered_tracks] == [t.uri for t in first.ordered_tracks]


def test_overflowing_protected_picks_fails_instead_of_silently_discarding_them():
    picks = [track(f"pick{i}", pos=i + 1, date=NOW.isoformat()) for i in range(101)]
    with pytest.raises(ValueError, match="protected"):
        build(picks, prior=[track("baseline")])


def test_known_empty_baseline_recognizes_first_manual_pick():
    pick = track("pick", pos=1, date=NOW.isoformat())
    result = build([pick], prior=[], state={"tracks": {}, "version": 2})
    assert pick.uri in result.protected_uris


def test_preview_builder_does_not_mutate_input_state():
    import copy
    first = build(current_list())
    before = copy.deepcopy(first.rotation_state)
    build(spotify_rewrite(first, NOW), state=first.rotation_state, now=NOW + timedelta(days=7))
    assert first.rotation_state == before


def test_manual_additions_consume_weekly_discovery_budget():
    current = current_list()
    adds = [track(f"pick{i}", pos=101+i, date=NOW.isoformat()) for i in range(24)]
    pool = [track(f"new{i}", date=NOW.isoformat()) for i in range(100)]
    result = build(current + adds, pool, prior=current)
    assert result.new_track_count == 1
    assert result.rotation_state["weekly_budget"]["used"] == 25
    remaining = spotify_rewrite(result, NOW)[1:]
    second = build(remaining, pool, prior=result.ordered_tracks, state=result.rotation_state,
                   now=NOW + timedelta(hours=1), update_mode="micro")
    assert second.new_track_count == 0


def test_master_only_song_never_receives_curator_protection():
    candidate = track("master-only", date=NOW.isoformat())
    result = build(current_list(), [candidate])
    assert candidate.uri in {t.uri for t in result.ordered_tracks}
    assert candidate.uri not in result.protected_uris


def test_deleted_song_variant_is_not_used_to_evade_rejection():
    current = current_list()
    first = build(current)
    deleted = current[0]
    alternate = replace(deleted, uri="spotify:track:alternate", current_position=None)
    second = build(current[1:], [alternate], prior=current, state=first.rotation_state)
    assert alternate.uri not in {t.uri for t in second.ordered_tracks}


def test_new_baseline_preserves_existing_membership_and_never_imports_stale_history():
    current = current_list()
    pool = [track(f"new{i}", date=NOW.isoformat()) for i in range(50)]
    first = build(current, pool, prior=[])
    assert first.bootstrap
    assert first.new_track_count == 0
    assert set(first.protected_uris) == {t.uri for t in current}


def test_small_target_also_bounds_the_front():
    result = build_cannabliss_playlist(master_tracks=[track(i) for i in range(20)],
        current_tracks=[], feeder_tracks=[], hall_tracks=[], target_size=3, weekly_insertions=25, now=NOW)
    assert len(result.ordered_tracks) == 3
