"""Tests for run-state cooldown persistence + previous-run URI reconstruction."""

from datetime import datetime, timezone

from src.cannabliss import (
    CannablissBuildResult,
    append_cannabliss_run,
    load_cannabliss_state,
    previous_run_track_uris,
)

NOW = datetime(2026, 6, 19, tzinfo=timezone.utc)


def _result(track_ids, removed_uris):
    tracks = []  # ordered_tracks not needed for these assertions
    return CannablissBuildResult(
        ordered_tracks=tracks,
        zones={"fresh_front": [], "body": []},
        summary={"track_ids_for_test": track_ids},
        new_track_count=0,
        update_mode="major",
        removed_uris=removed_uris,
    )


def test_previous_run_track_uris_reconstructs_uris():
    state = {"runs": [{"timestamp": "t", "track_ids": ["aaa", "bbb"]}]}
    assert previous_run_track_uris(state) == {"spotify:track:aaa", "spotify:track:bbb"}


def test_previous_run_track_uris_empty_when_no_runs():
    assert previous_run_track_uris({"runs": []}) == set()


def test_append_run_records_cooldown(tmp_path):
    path = str(tmp_path / "state.json")
    result = CannablissBuildResult(
        ordered_tracks=[], zones={"fresh_front": [], "body": []},
        summary={}, new_track_count=0, update_mode="major",
        removed_uris=["spotify:track:gone"],
    )
    append_cannabliss_run(result, path=path, now=NOW, cooldown_days=7)
    state = load_cannabliss_state(path)
    assert [e["uri"] for e in state["cooldown"]] == ["spotify:track:gone"]
    assert state["cooldown"][0]["removed_at"] == NOW.isoformat()
