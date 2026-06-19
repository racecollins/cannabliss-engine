"""Tests for Cannabliss curated playlist construction (fresh-front model)."""

from datetime import datetime, timezone

from src.cannabliss import CannablissTrack, ListeningSignals, build_cannabliss_playlist


def _track(i, *, source_tags=None, added_at="2026-06-01T00:00:00Z",
           current_position=None, popularity=50, release_date="2026-06-01", artist=None):
    return CannablissTrack(
        uri=f"spotify:track:{i}",
        name=f"Song {i}",
        artists=artist or f"Artist {i}",
        added_at=added_at,
        source_tags=source_tags or {"master"},
        current_position=current_position,
        popularity=popularity,
        release_date=release_date,
    )


NOW = datetime(2026, 6, 19, tzinfo=timezone.utc)


def _existing_playlist(n, *, added_at="2026-06-12T00:00:00Z"):
    """A live playlist of `n` tracks the engine wrote last run (uniform added_at)."""
    return [
        _track(i, source_tags={"current", "master"}, added_at=added_at,
               current_position=i + 1, artist=f"Current Artist {i}")
        for i in range(n)
    ]


def test_weekly_adds_become_the_front_newest_first():
    current = _existing_playlist(100)
    adds = [
        _track(900 + k, source_tags={"current"}, current_position=100 + k,
               added_at=f"2026-06-{14 + k:02d}T00:00:00Z", artist=f"Add Artist {k}")
        for k in range(4)
    ]
    prev = {t.uri for t in current}
    result = build_cannabliss_playlist(
        master_tracks=current + adds,
        current_tracks=current + adds,
        feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25,
        previous_track_uris=prev, now=NOW,
    )
    front_uris = [t.uri for t in result.zones["fresh_front"]]
    # Newest add (k=3, 2026-06-17) leads.
    assert front_uris[0] == "spotify:track:903"
    assert {t.uri for t in adds} <= set(front_uris)
    assert len(result.ordered_tracks) == 100


def test_hot_pick_add_lands_in_top_5():
    current = _existing_playlist(100)
    plain_adds = [
        _track(900 + k, source_tags={"current"}, current_position=100 + k,
               added_at=f"2026-06-{16 + 0:02d}T00:00:00Z", artist=f"Add Artist {k}")
        for k in range(6)
    ]
    hot_add = _track(950, source_tags={"current"}, current_position=120,
                     added_at="2026-06-14T00:00:00Z", artist="Hot Artist")
    prev = {t.uri for t in current}
    result = build_cannabliss_playlist(
        master_tracks=current + plain_adds + [hot_add],
        current_tracks=current + plain_adds + [hot_add],
        feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25,
        previous_track_uris=prev,
        listening_signals=ListeningSignals(top_track_ids=frozenset({"950"}), top_tracks_boost=0.4),
        now=NOW,
    )
    top_5 = {t.uri for t in result.ordered_tracks[:5]}
    assert hot_add.uri in top_5


def test_rolling_fill_when_fewer_than_fifteen_adds():
    current = _existing_playlist(100, added_at="2026-06-05T00:00:00Z")
    adds = [
        _track(900 + k, source_tags={"current"}, current_position=100 + k,
               added_at="2026-06-18T00:00:00Z", artist=f"Add Artist {k}")
        for k in range(8)
    ]
    prev = {t.uri for t in current}
    result = build_cannabliss_playlist(
        master_tracks=current + adds, current_tracks=current + adds,
        feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25,
        previous_track_uris=prev, fresh_front_size=15, now=NOW,
    )
    front = result.zones["fresh_front"]
    assert len(front) == 15
    assert {t.uri for t in adds} <= {t.uri for t in front[:8]}


def test_artist_binge_capped_in_front_but_all_kept():
    current = _existing_playlist(100, added_at="2026-06-05T00:00:00Z")
    binge = [
        _track(900 + k, source_tags={"current"}, current_position=100 + k,
               added_at=f"2026-06-{12 + k:02d}T00:00:00Z", artist="Binge Artist")
        for k in range(6)
    ]
    prev = {t.uri for t in current}
    result = build_cannabliss_playlist(
        master_tracks=current + binge, current_tracks=current + binge,
        feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25,
        previous_track_uris=prev, fresh_front_max_per_artist=2, now=NOW,
    )
    front_binge = [t for t in result.zones["fresh_front"] if t.artists == "Binge Artist"]
    assert len(front_binge) == 2
    kept = {t.uri for t in result.ordered_tracks}
    assert {t.uri for t in binge} <= kept  # none discarded


def test_protected_adds_survive_trim_and_oldest_retire():
    current = _existing_playlist(100, added_at="2026-06-12T00:00:00Z")
    # 20 weekly adds push the playlist to 120; trim back to 100 must keep the adds.
    adds = [
        _track(900 + k, source_tags={"current"}, current_position=100 + k,
               added_at="2026-06-18T00:00:00Z", artist=f"Add Artist {k}")
        for k in range(20)
    ]
    prev = {t.uri for t in current}
    result = build_cannabliss_playlist(
        master_tracks=current + adds, current_tracks=current + adds,
        feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25,
        previous_track_uris=prev, now=NOW,
    )
    kept = {t.uri for t in result.ordered_tracks}
    assert {t.uri for t in adds} <= kept
    assert len(result.ordered_tracks) == 100
    assert len(result.removed_uris) >= 20  # 20 oldest incumbents retired


def test_cooldown_excludes_removed_song_from_refill():
    current = _existing_playlist(60, added_at="2026-06-12T00:00:00Z")
    benched = _track(7777, source_tags={"master"}, added_at="2026-06-18T00:00:00Z")
    prev = {t.uri for t in current}
    result = build_cannabliss_playlist(
        master_tracks=current + [benched], current_tracks=current,
        feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25,
        previous_track_uris=prev, cooldown_uris={benched.uri}, now=NOW,
    )
    assert benched.uri not in {t.uri for t in result.ordered_tracks}


def test_cooldown_overridden_by_manual_readd():
    current = _existing_playlist(60, added_at="2026-06-12T00:00:00Z")
    readded = _track(7777, source_tags={"current"}, current_position=61,
                     added_at="2026-06-18T00:00:00Z")
    prev = {t.uri for t in current}  # readded is NOT in prev => it's a weekly add
    result = build_cannabliss_playlist(
        master_tracks=current + [readded], current_tracks=current + [readded],
        feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25,
        previous_track_uris=prev, cooldown_uris={readded.uri}, now=NOW,
    )
    assert readded.uri in {t.uri for t in result.ordered_tracks[:15]}


def test_user_removed_song_recorded_for_cooldown():
    current = _existing_playlist(100, added_at="2026-06-12T00:00:00Z")
    # Race deleted a track during the week: it's in the previous run but no longer
    # in the live playlist (id 500 is outside the 0..99 range of `current`).
    deleted_uri = "spotify:track:500"
    prev = {t.uri for t in current} | {deleted_uri}
    result = build_cannabliss_playlist(
        master_tracks=current, current_tracks=current,
        feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25,
        previous_track_uris=prev, now=NOW,
    )
    assert deleted_uri in result.removed_uris


def test_hall_track_sits_below_equivalent_non_hall_in_body():
    # Fresh incumbents fill the front, so hall + plain land in the body where the
    # Hall penalty applies. plain has the *lower* uri, so only the penalty can
    # explain plain ranking above hall (uri tiebreak alone would favor hall).
    current = _existing_playlist(20, added_at="2026-06-18T00:00:00Z")
    plain = _track(8000, source_tags={"master"}, added_at="2026-06-01T00:00:00Z", popularity=50)
    hall = _track(8001, source_tags={"hall"}, added_at="2026-06-01T00:00:00Z", popularity=50)
    prev = {t.uri for t in current}
    result = build_cannabliss_playlist(
        master_tracks=current + [plain, hall],
        current_tracks=current,
        feeder_tracks=[], hall_tracks=[hall],
        target_size=100, weekly_insertions=25,
        previous_track_uris=prev, now=NOW,
    )
    order = [t.uri for t in result.ordered_tracks]
    assert order.index(plain.uri) < order.index(hall.uri)


def test_zones_are_two_tiers_partitioning_the_playlist():
    current = _existing_playlist(100, added_at="2026-06-12T00:00:00Z")
    prev = {t.uri for t in current}
    result = build_cannabliss_playlist(
        master_tracks=current, current_tracks=current,
        feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25,
        previous_track_uris=prev, now=NOW,
    )
    assert set(result.zones.keys()) == {"fresh_front", "body"}
    combined = [t.uri for t in result.zones["fresh_front"]] + [t.uri for t in result.zones["body"]]
    assert combined == [t.uri for t in result.ordered_tracks]


def test_micro_promotes_adds_and_preserves_everything():
    current = _existing_playlist(100, added_at="2026-06-12T00:00:00Z")
    adds = [
        _track(900 + k, source_tags={"current"}, current_position=100 + k,
               added_at="2026-06-18T00:00:00Z", artist=f"Add Artist {k}")
        for k in range(3)
    ]
    new_master = [
        _track(3000 + k, source_tags={"master"}, added_at="2026-06-17T00:00:00Z",
               artist=f"New Artist {k}")
        for k in range(10)
    ]
    prev = {t.uri for t in current}
    result = build_cannabliss_playlist(
        master_tracks=current + adds + new_master,
        current_tracks=current + adds,
        feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25,
        update_mode="micro", micro_refresh_count=5,
        previous_track_uris=prev, now=NOW,
    )
    # All current tracks preserved (no retirement in micro).
    assert {t.uri for t in current + adds} <= {t.uri for t in result.ordered_tracks}
    assert result.removed_uris == []
    # Weekly adds promoted to the front.
    assert {t.uri for t in adds} <= {t.uri for t in result.zones["fresh_front"]}


def test_initial_build_hits_target_size_from_master():
    master = [
        _track(i, added_at=f"2026-06-{(i % 28) + 1:02d}T00:00:00Z", artist=f"Artist {i}")
        for i in range(220)
    ]
    result = build_cannabliss_playlist(
        master_tracks=master, current_tracks=[],
        feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25, now=NOW,
    )
    assert len(result.ordered_tracks) == 100
    assert len(result.zones["fresh_front"]) == 15
    assert len(result.zones["body"]) == 85
