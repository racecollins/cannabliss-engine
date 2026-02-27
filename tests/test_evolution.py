"""Tests for evolutionary candidate generation and scoring."""

from src.evolution import (
    Candidate,
    ScoreWeights,
    choose_winner,
    generate_candidates,
    score_candidate,
    track_id_from_uri,
)
from src.selection import Track


def _track(i: int, artist: str = "Artist", added_at: str = "2026-01-01T00:00:00Z") -> Track:
    return Track(
        uri=f"spotify:track:{i}",
        name=f"Song {i}",
        artists=artist,
        added_at=added_at,
    )


def test_generate_candidates_k_and_count():
    tracks = [_track(i, artist=f"Artist{i}") for i in range(250)]
    out = generate_candidates(
        tracks,
        mode="random",
        count=100,
        candidates=7,
        seed_base=10,
        history_runs=[],
        history_weeks=6,
        max_tracks_per_artist=2,
        fresh_days_1=30,
        fresh_days_2=180,
    )
    assert len(out) == 7
    assert all(len(c.tracks) == 100 for c in out)


def test_generate_candidates_deterministic_seed_base():
    tracks = [_track(i, artist=f"A{i}") for i in range(220)]
    kwargs = dict(
        tracks=tracks,
        mode="random",
        count=50,
        candidates=5,
        seed_base=1234,
        history_runs=[],
        history_weeks=6,
        max_tracks_per_artist=2,
        fresh_days_1=30,
        fresh_days_2=180,
    )
    c1 = generate_candidates(**kwargs)
    c2 = generate_candidates(**kwargs)
    ids1 = [[track_id_from_uri(t.uri) for t in c.tracks] for c in c1]
    ids2 = [[track_id_from_uri(t.uri) for t in c.tracks] for c in c2]
    assert ids1 == ids2


def test_scoring_prefers_higher_diversity():
    weights = ScoreWeights(novelty=0.0, diversity=1.0, cohesion=0.0, freshness=0.0)
    high_div = Candidate(
        id="a",
        seed=1,
        tracks=[_track(1, "A"), _track(2, "B"), _track(3, "C"), _track(4, "D")],
    )
    low_div = Candidate(
        id="b",
        seed=2,
        tracks=[_track(5, "A"), _track(6, "A"), _track(7, "A"), _track(8, "A")],
    )
    audio = {}
    scored_a = score_candidate(high_div, recent_ids=set(), audio_features=audio, weights=weights)
    scored_b = score_candidate(low_div, recent_ids=set(), audio_features=audio, weights=weights)
    assert scored_a.score > scored_b.score


def test_scoring_prefers_higher_novelty():
    weights = ScoreWeights(novelty=1.0, diversity=0.0, cohesion=0.0, freshness=0.0)
    a = Candidate(id="a", seed=1, tracks=[_track(1), _track(2), _track(3), _track(4)])
    b = Candidate(id="b", seed=2, tracks=[_track(5), _track(6), _track(7), _track(8)])
    recent_ids = {"5", "6", "7", "8"}
    scored_a = score_candidate(a, recent_ids=recent_ids, audio_features={}, weights=weights)
    scored_b = score_candidate(b, recent_ids=recent_ids, audio_features={}, weights=weights)
    assert scored_a.score > scored_b.score


def test_scoring_prefers_lower_feature_variance_for_cohesion():
    weights = ScoreWeights(novelty=0.0, diversity=0.0, cohesion=1.0, freshness=0.0)
    tight = Candidate(id="tight", seed=1, tracks=[_track(1), _track(2), _track(3), _track(4)])
    wide = Candidate(id="wide", seed=2, tracks=[_track(5), _track(6), _track(7), _track(8)])
    audio = {
        "1": {"energy": 0.5, "danceability": 0.5, "valence": 0.5, "tempo": 120.0},
        "2": {"energy": 0.51, "danceability": 0.49, "valence": 0.5, "tempo": 121.0},
        "3": {"energy": 0.5, "danceability": 0.5, "valence": 0.49, "tempo": 119.5},
        "4": {"energy": 0.5, "danceability": 0.5, "valence": 0.51, "tempo": 120.5},
        "5": {"energy": 0.1, "danceability": 0.9, "valence": 0.2, "tempo": 80.0},
        "6": {"energy": 0.9, "danceability": 0.1, "valence": 0.8, "tempo": 160.0},
        "7": {"energy": 0.2, "danceability": 0.8, "valence": 0.3, "tempo": 90.0},
        "8": {"energy": 0.8, "danceability": 0.2, "valence": 0.7, "tempo": 150.0},
    }
    scored_tight = score_candidate(tight, recent_ids=set(), audio_features=audio, weights=weights)
    scored_wide = score_candidate(wide, recent_ids=set(), audio_features=audio, weights=weights)
    assert scored_tight.score > scored_wide.score
    assert choose_winner([scored_wide, scored_tight]).id == "tight"

