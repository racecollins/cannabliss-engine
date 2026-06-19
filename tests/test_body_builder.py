"""Tests for the body builder."""

from datetime import datetime, timezone

from src.cannabliss import CannablissTrack, ListeningSignals, _build_body

NOW = datetime(2026, 6, 19, tzinfo=timezone.utc)


def _t(i, *, added_at="2026-01-01T00:00:00Z", artist=None, current_position=None,
       popularity=50, source_tags=None):
    return CannablissTrack(
        uri=f"spotify:track:{i}",
        name=f"Song {i}",
        artists=artist or f"Artist {i}",
        added_at=added_at,
        source_tags=source_tags or {"current", "master"},
        current_position=current_position,
        popularity=popularity,
        release_date="2024-01-01",
    )


def test_protected_overflow_sits_at_top_of_body():
    protected = [_t(1, added_at="2026-06-18T00:00:00Z")]
    candidates = [_t(100 + i, current_position=i + 1) for i in range(10)]
    body = _build_body(
        protected_overflow=protected, candidates=candidates, slots=6,
        max_per_artist=2, front_tracks=[], signals=ListeningSignals(), now=NOW,
    )
    assert body[0].uri == "spotify:track:1"
    assert len(body) == 6


def test_incumbents_hold_relative_order_on_score_ties():
    # Uniform added_at + no listening => same body_score; stability tiebreaker decides.
    candidates = [
        _t(1, current_position=80),
        _t(2, current_position=10),
        _t(3, current_position=45),
    ]
    body = _build_body(
        protected_overflow=[], candidates=candidates, slots=3,
        max_per_artist=2, front_tracks=[], signals=ListeningSignals(), now=NOW,
    )
    assert [t.uri for t in body] == ["spotify:track:2", "spotify:track:3", "spotify:track:1"]


def test_body_respects_artist_cap_seeded_from_front():
    front = [_t(1, artist="Repeat"), _t(2, artist="Repeat")]  # already 2 in the front
    candidates = [_t(3, artist="Repeat", current_position=5), _t(4, artist="Other", current_position=6)]
    body = _build_body(
        protected_overflow=[], candidates=candidates, slots=5,
        max_per_artist=2, front_tracks=front, signals=ListeningSignals(), now=NOW,
    )
    assert "spotify:track:3" not in {t.uri for t in body}  # Repeat already at cap via front
    assert "spotify:track:4" in {t.uri for t in body}
