"""Tests for Cannabliss rolling playlist construction."""

from datetime import datetime, timezone

from src.cannabliss import CannablissTrack, ListeningSignals, build_cannabliss_playlist


def _track(
    i: int,
    *,
    source_tags: set[str] | None = None,
    added_at: str = "2026-01-01T00:00:00Z",
    current_position: int | None = None,
    popularity: int = 50,
    release_date: str = "2026-01-01",
    artist: str | None = None,
) -> CannablissTrack:
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


def test_build_initial_playlist_hits_target_size():
    master = [
        _track(i, added_at=f"2026-01-{(i % 28) + 1:02d}T00:00:00Z")
        for i in range(220)
    ]
    result = build_cannabliss_playlist(
        master_tracks=master,
        current_tracks=[],
        feeder_tracks=[],
        hall_tracks=[],
        target_size=160,
        weekly_insertions=40,
        now=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )

    assert len(result.ordered_tracks) == 160
    assert len(result.zones["premium_current"]) == 10
    assert len(result.zones["high_conviction"]) == 15
    assert len(result.zones["discovery"]) == 15


def test_build_existing_playlist_keeps_weekly_insertions_to_40():
    current = [
        _track(
            i,
            source_tags={"current", "master"},
            added_at="2025-11-01T00:00:00Z",
            current_position=i + 1,
            popularity=40,
            release_date="2024-01-01",
        )
        for i in range(160)
    ]
    new_master = [
        _track(
            1000 + i,
            source_tags={"master"},
            added_at=f"2026-02-{(i % 28) + 1:02d}T00:00:00Z",
            popularity=70,
            release_date="2026-02-01",
        )
        for i in range(80)
    ]
    result = build_cannabliss_playlist(
        master_tracks=current + new_master,
        current_tracks=current,
        feeder_tracks=[],
        hall_tracks=[],
        target_size=160,
        weekly_insertions=40,
        now=datetime(2026, 2, 15, tzinfo=timezone.utc),
    )

    assert len(result.summary["added"]) == 40
    assert len(result.ordered_tracks) == 160


def test_top_ten_prefers_recent_current_songs_over_stale_library():
    recent = [
        _track(
            200 + i,
            source_tags={"master", "feeder:lorem"},
            added_at=f"2026-03-{i + 1:02d}T00:00:00Z",
            popularity=80,
            release_date="2026-03-01",
        )
        for i in range(15)
    ]
    stale = [
        _track(
            i,
            source_tags={"master"},
            added_at="2024-01-01T00:00:00Z",
            popularity=10,
            release_date="2018-01-01",
        )
        for i in range(40)
    ]
    result = build_cannabliss_playlist(
        master_tracks=recent + stale,
        current_tracks=[],
        feeder_tracks=[],
        hall_tracks=[],
        target_size=40,
        weekly_insertions=20,
        now=datetime(2026, 3, 20, tzinfo=timezone.utc),
    )

    top_ids = {track.uri for track in result.zones["premium_current"]}
    recent_ids = {track.uri for track in recent}
    assert len(top_ids & recent_ids) >= 8


def test_stabilizer_zone_interleaves_incumbents_and_new_tracks():
    current = [
        _track(
            i,
            source_tags={"current", "master"},
            added_at="2025-12-01T00:00:00Z",
            current_position=i + 1,
            popularity=60,
            release_date="2025-01-01",
        )
        for i in range(160)
    ]
    feeder = [
        _track(
            500 + i,
            source_tags={"feeder:antipop"},
            added_at=f"2026-03-{i + 1:02d}T00:00:00Z",
            popularity=65,
            release_date="2026-03-01",
        )
        for i in range(40)
    ]
    result = build_cannabliss_playlist(
        master_tracks=current + feeder,
        current_tracks=current,
        feeder_tracks=feeder,
        hall_tracks=[],
        target_size=160,
        weekly_insertions=40,
        now=datetime(2026, 3, 20, tzinfo=timezone.utc),
    )

    stabilizers = result.zones["stabilizers"]
    assert any(track.current_position is not None for track in stabilizers)
    front_half = result.ordered_tracks[:80]
    assert any(track.current_position is None for track in front_half)
    assert any(track.current_position is not None for track in front_half)


def test_top_track_signal_can_promote_older_rediscovery():
    old_favorite = _track(
        999,
        source_tags={"master"},
        added_at="2025-12-01T00:00:00Z",
        popularity=40,
        release_date="2014-01-01",
        artist="Special Artist",
    )
    others = [
        _track(
            i,
            source_tags={"master"},
            added_at=f"2026-03-{(i % 20) + 1:02d}T00:00:00Z",
            popularity=30,
            release_date="2026-03-01",
        )
        for i in range(40)
    ]

    result_without = build_cannabliss_playlist(
        master_tracks=[old_favorite] + others,
        current_tracks=[],
        feeder_tracks=[],
        hall_tracks=[],
        target_size=40,
        weekly_insertions=20,
        now=datetime(2026, 3, 20, tzinfo=timezone.utc),
    )
    result_with = build_cannabliss_playlist(
        master_tracks=[old_favorite] + others,
        current_tracks=[],
        feeder_tracks=[],
        hall_tracks=[],
        target_size=40,
        weekly_insertions=20,
        listening_signals=ListeningSignals(
            top_track_ids=frozenset({"999"}),
            top_tracks_boost=0.8,
        ),
        now=datetime(2026, 3, 20, tzinfo=timezone.utc),
    )

    without_top_10 = {track.uri for track in result_without.zones["premium_current"]}
    with_top_10 = {track.uri for track in result_with.zones["premium_current"]}
    assert old_favorite.uri not in without_top_10
    assert old_favorite.uri in with_top_10


def test_recently_played_signal_can_help_front_half_placement():
    focus_track = _track(
        888,
        source_tags={"master"},
        added_at="2026-02-01T00:00:00Z",
        popularity=20,
        release_date="2020-01-01",
        artist="Focus Artist",
    )
    others = [
        _track(
            i,
            source_tags={"master"},
            added_at="2026-02-10T00:00:00Z",
            popularity=20,
            release_date="2026-01-01",
            artist=f"Artist {i}",
        )
        for i in range(60)
    ]

    result = build_cannabliss_playlist(
        master_tracks=[focus_track] + others,
        current_tracks=[],
        feeder_tracks=[],
        hall_tracks=[],
        target_size=50,
        weekly_insertions=20,
        listening_signals=ListeningSignals(
            recently_played_ids=frozenset({"888"}),
            recently_played_boost=0.8,
        ),
        now=datetime(2026, 3, 20, tzinfo=timezone.utc),
    )

    front_half_ids = {track.uri for track in result.ordered_tracks[:40]}
    assert focus_track.uri in front_half_ids


def test_top_10_prefers_signaled_listens_when_available():
    signaled = [
        _track(
            1000 + i,
            source_tags={"master"},
            added_at="2025-12-01T00:00:00Z",
            popularity=20,
            release_date="2018-01-01",
            artist=f"Signal Artist {i}",
        )
        for i in range(12)
    ]
    fresh_unsignaled = [
        _track(
            i,
            source_tags={"master"},
            added_at=f"2026-03-{(i % 20) + 1:02d}T00:00:00Z",
            popularity=90,
            release_date="2026-03-01",
            artist=f"Fresh Artist {i}",
        )
        for i in range(40)
    ]

    result = build_cannabliss_playlist(
        master_tracks=signaled + fresh_unsignaled,
        current_tracks=[],
        feeder_tracks=[],
        hall_tracks=[],
        target_size=50,
        weekly_insertions=20,
        listening_signals=ListeningSignals(
            top_track_ids=frozenset({track.uri.rsplit(":", 1)[-1] for track in signaled}),
            top_tracks_boost=0.8,
        ),
        now=datetime(2026, 3, 20, tzinfo=timezone.utc),
    )

    top_10_uris = {track.uri for track in result.zones["premium_current"]}
    signaled_uris = {track.uri for track in signaled}
    assert top_10_uris <= signaled_uris


def test_top_10_falls_back_when_signaled_pool_is_small():
    signaled = [
        _track(
            2000 + i,
            source_tags={"master"},
            added_at="2025-12-01T00:00:00Z",
            popularity=20,
            release_date="2019-01-01",
            artist=f"Signal Artist {i}",
        )
        for i in range(3)
    ]
    fresh_unsignaled = [
        _track(
            i,
            source_tags={"master"},
            added_at=f"2026-03-{(i % 20) + 1:02d}T00:00:00Z",
            popularity=90,
            release_date="2026-03-01",
            artist=f"Fresh Artist {i}",
        )
        for i in range(40)
    ]

    result = build_cannabliss_playlist(
        master_tracks=signaled + fresh_unsignaled,
        current_tracks=[],
        feeder_tracks=[],
        hall_tracks=[],
        target_size=50,
        weekly_insertions=20,
        listening_signals=ListeningSignals(
            recently_played_ids=frozenset({track.uri.rsplit(":", 1)[-1] for track in signaled}),
            recently_played_boost=0.8,
        ),
        now=datetime(2026, 3, 20, tzinfo=timezone.utc),
    )

    assert len(result.zones["premium_current"]) == 10
    top_10_uris = {track.uri for track in result.zones["premium_current"]}
    signaled_uris = {track.uri for track in signaled}
    assert len(top_10_uris & signaled_uris) == 3


def test_dedupes_same_song_variants_by_artist_and_title():
    variant_a = _track(
        1,
        source_tags={"master"},
        added_at="2026-03-10T00:00:00Z",
        popularity=20,
        release_date="2026-03-01",
        artist="070 Shake",
    )
    variant_a.name = "Skin and Bones"
    variant_b = _track(
        2,
        source_tags={"master"},
        added_at="2026-03-11T00:00:00Z",
        popularity=30,
        release_date="2026-03-01",
        artist="070 Shake",
    )
    variant_b.name = "Skin and Bones - acoustic"
    others = [_track(100 + i) for i in range(60)]

    result = build_cannabliss_playlist(
        master_tracks=[variant_a, variant_b] + others,
        current_tracks=[],
        feeder_tracks=[],
        hall_tracks=[],
        target_size=50,
        weekly_insertions=20,
        now=datetime(2026, 3, 20, tzinfo=timezone.utc),
    )

    matches = [
        track for track in result.ordered_tracks
        if track.artists == "070 Shake" and "skin and bones" in track.name.lower()
    ]
    assert len(matches) == 1


def test_top_25_has_max_one_track_per_primary_artist_and_top_50_has_max_two():
    dominant_artist_tracks = [
        _track(
            i,
            source_tags={"master"},
            added_at=f"2026-03-{(i % 20) + 1:02d}T00:00:00Z",
            popularity=80,
            release_date="2026-03-01",
            artist="Repeat Artist",
        )
        for i in range(20)
    ]
    diverse_tracks = [
        _track(
            100 + i,
            source_tags={"master"},
            added_at=f"2026-03-{(i % 20) + 1:02d}T00:00:00Z",
            popularity=60,
            release_date="2026-03-01",
            artist=f"Artist {i}",
        )
        for i in range(80)
    ]

    result = build_cannabliss_playlist(
        master_tracks=dominant_artist_tracks + diverse_tracks,
        current_tracks=[],
        feeder_tracks=[],
        hall_tracks=[],
        target_size=80,
        weekly_insertions=40,
        now=datetime(2026, 3, 20, tzinfo=timezone.utc),
    )

    top_25_repeat = [
        track for track in result.ordered_tracks[:25]
        if track.artists == "Repeat Artist"
    ]
    top_50_repeat = [
        track for track in result.ordered_tracks[:50]
        if track.artists == "Repeat Artist"
    ]
    assert len(top_25_repeat) <= 1
    assert len(top_50_repeat) <= 2
