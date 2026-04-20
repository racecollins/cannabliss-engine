"""Tests for the Cannabliss main orchestration flow."""

from types import SimpleNamespace

from src.main import run_cannabliss


class _FakeClient:
    def get_top_track_ids(self, time_range: str, limit: int):
        raise AssertionError("top tracks should not be loaded in this test")

    def get_recently_played_track_ids(self, limit: int):
        raise AssertionError("recently played should not be loaded in this test")

    def replace_playlist_tracks(self, playlist_id: str, uris: list[str]) -> None:
        raise AssertionError("dry run should not write to Spotify")


def _cfg(**overrides):
    base = {
        "profile": "cannabliss",
        "dry_run": True,
        "master_playlist_id": "master123",
        "cannabliss_target_playlist_id": "target123",
        "cannabliss_hall_of_fame_playlist_id": "",
        "cannabliss_feeder_playlist_ids": (),
        "cannabliss_target_size": 10,
        "cannabliss_weekly_insertions": 2,
        "cannabliss_update_mode": "major",
        "cannabliss_micro_refresh_count": 1,
        "max_tracks_per_artist": 2,
        "cannabliss_use_top_tracks": False,
        "cannabliss_use_recently_played": False,
        "cannabliss_top_tracks_term": "short_term",
        "cannabliss_top_tracks_limit": 50,
        "cannabliss_recently_played_limit": 50,
        "cannabliss_top_tracks_boost": 0.35,
        "cannabliss_recently_played_boost": 0.25,
        "playlist_cache_dir": "data/cache/playlists",
        "playlist_cache_ttl_hours": 12,
        "force_refresh": False,
        "cannabliss_state_path": "data/cannabliss_state.json",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_run_cannabliss_always_refreshes_live_target_playlist(monkeypatch, tmp_path):
    cfg = _cfg(cannabliss_state_path=str(tmp_path / "state.json"))
    calls: list[dict] = []

    def fake_get_cached_playlist_items(client, playlist_id: str, *, cache_dir: str, ttl_hours: int, force_refresh: bool = False):
        calls.append({"playlist_id": playlist_id, "force_refresh": force_refresh})
        return []

    monkeypatch.setattr("src.main.get_cached_playlist_items", fake_get_cached_playlist_items)
    monkeypatch.setattr("src.main.parse_source_items", lambda items, source_tag, current_order=False: [])
    monkeypatch.setattr(
        "src.main.build_cannabliss_playlist",
        lambda **kwargs: SimpleNamespace(
            ordered_tracks=[],
            zones={},
            summary={},
            new_track_count=0,
            update_mode=kwargs["update_mode"],
        ),
    )
    monkeypatch.setattr("src.main.append_cannabliss_run", lambda result, path: None)

    run_cannabliss(cfg, _FakeClient())

    assert calls[0] == {"playlist_id": "master123", "force_refresh": False}
    assert calls[1] == {"playlist_id": "target123", "force_refresh": True}
