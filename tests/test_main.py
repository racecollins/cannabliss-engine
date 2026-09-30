"""Tests for the Cannabliss main orchestration flow."""

from types import SimpleNamespace
import pytest


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("CANNABLISS_GIT_STATE", raising=False)


from src.main import _print_spotify_error_help, run_cannabliss
from src.spotify_client import SpotifyApiError, SpotifyAuthError


def test_error_help_shows_reauth_steps_for_expired_token(capsys):
    """When the refresh token expires, the failure must tell the operator
    exactly how to recover, not just print a bare 400."""
    err = SpotifyAuthError(
        "POST", "https://accounts.spotify.com/api/token", 400, "invalid_grant"
    )
    _print_spotify_error_help(err)

    out = capsys.readouterr().err
    assert "refresh_token_helper" in out
    assert "SPOTIFY_REFRESH_TOKEN" in out


def test_error_help_stays_quiet_for_unrelated_errors(capsys):
    """A generic non-403, non-auth error should not emit re-auth noise."""
    err = SpotifyApiError("GET", "https://api.spotify.com/v1/me", 500, "server error")
    _print_spotify_error_help(err)

    out = capsys.readouterr().err
    assert "refresh_token_helper" not in out


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
        "cannabliss_fresh_front_size": 15,
        "cannabliss_fresh_front_max_per_artist": 2,
        "cannabliss_removal_cooldown_days": 7,
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
    monkeypatch.setattr("src.main.append_cannabliss_run", lambda result, path=None, now=None, cooldown_days=None: None)

    run_cannabliss(cfg, _FakeClient())

    assert calls[0] == {"playlist_id": "master123", "force_refresh": False}
    assert calls[1] == {"playlist_id": "target123", "force_refresh": True}


def _item(i):
    return {"added_at": "2026-09-25T00:00:00Z", "track": {
        "type": "track", "uri": f"spotify:track:{i}", "name": f"Song {i}",
        "artists": [{"name": f"Artist {i}"}]}}


def test_dry_run_does_not_create_history(monkeypatch, tmp_path):
    path = tmp_path / "state.json"
    monkeypatch.setattr("src.main.get_cached_playlist_items", lambda *a, **k: [_item(1)])
    run_cannabliss(_cfg(cannabliss_state_path=str(path)), _FakeClient())
    assert not path.exists()


def test_dry_run_leaves_existing_history_byte_identical(monkeypatch, tmp_path):
    path = tmp_path / "state.json"
    original = '{"runs": [], "schema_version": 2, "rotation": {"version": 2, "tracks": {}}}'
    path.write_text(original)
    monkeypatch.setattr("src.main.get_cached_playlist_items", lambda *a, **k: [_item(1)])
    run_cannabliss(_cfg(cannabliss_state_path=str(path)), _FakeClient())
    assert path.read_text() == original


def test_failed_spotify_write_does_not_record_success(monkeypatch, tmp_path):
    import pytest
    path = tmp_path / "state.json"
    path.write_text('{"runs": []}')
    class Client:
        def get_all_playlist_items(self, playlist_id):
            return [_item(1)]
        def replace_playlist_tracks(self, playlist_id, uris):
            raise SpotifyApiError("PUT", "spotify", 500, "failed")
    monkeypatch.setattr("src.main.get_cached_playlist_items", lambda *a, **k: [_item(1)])
    with pytest.raises(SystemExit):
        run_cannabliss(_cfg(dry_run=False, cannabliss_state_path=str(path)), Client())
    assert path.read_text() == '{"runs": []}'
    import json
    pending = json.loads((tmp_path / 'state.json.pending.json').read_text())
    assert 'proposed_rotation' in pending  # Includes queue metadata before any Spotify write.


def test_success_saved_only_after_readback_matches(monkeypatch, tmp_path):
    import json
    path = tmp_path / "state.json"
    class Client:
        written = False
        def get_all_playlist_items(self, playlist_id):
            assert not path.exists()
            return [_item(1)]
        def replace_playlist_tracks(self, playlist_id, uris):
            assert not path.exists()
            self.written = True
    client = Client()
    monkeypatch.setattr("src.main.get_cached_playlist_items", lambda *a, **k: [_item(1)])
    run_cannabliss(_cfg(dry_run=False, cannabliss_state_path=str(path)), client)
    assert client.written
    assert json.loads(path.read_text())["schema_version"] == 2


def test_concurrent_edit_aborts_write(monkeypatch, tmp_path):
    import pytest
    class Client(_FakeClient):
        def get_all_playlist_items(self, playlist_id):
            return [_item(1), _item(2)]
    monkeypatch.setattr("src.main.get_cached_playlist_items", lambda *a, **k: [_item(1)])
    with pytest.raises(RuntimeError, match="changed"):
        run_cannabliss(_cfg(dry_run=False, cannabliss_state_path=str(tmp_path / "state.json")), Client())


def test_mismatched_readback_does_not_save_state(monkeypatch, tmp_path):
    import pytest
    path = tmp_path / "state.json"
    class Client:
        written = False
        def get_all_playlist_items(self, playlist_id):
            return [] if self.written else [_item(1)]
        def replace_playlist_tracks(self, playlist_id, uris):
            self.written = True
    monkeypatch.setattr("src.main.get_cached_playlist_items", lambda *a, **k: [_item(1)])
    with pytest.raises(RuntimeError, match="verification"):
        run_cannabliss(_cfg(dry_run=False, cannabliss_state_path=str(path)), Client())
    assert not path.exists()


def test_unresolved_local_write_blocks_retry_before_reading_spotify(tmp_path):
    import pytest
    path = tmp_path / "state.json"
    (tmp_path / "state.json.pending.json").write_text('{}')
    with pytest.raises(RuntimeError, match="pending update"):
        run_cannabliss(_cfg(cannabliss_state_path=str(path)), _FakeClient())


def test_preview_contains_song_names_positions_and_removals(monkeypatch, tmp_path):
    import json
    cfg = _cfg(cannabliss_state_path=str(tmp_path / "state.json"),
               cannabliss_preview_path=str(tmp_path / "preview.md"))
    monkeypatch.setattr("src.main.get_cached_playlist_items", lambda *a, **k: [_item(1)])
    run_cannabliss(cfg, _FakeClient())
    preview = json.loads((tmp_path / "preview.json").read_text())
    assert preview["preview_only"] is True
    assert preview["tracks"][0]["name"] == "Song 1"
    assert preview["tracks"][0]["previous_position"] == 1
    assert not (tmp_path / "state.json").exists()


def test_live_actions_requires_durable_history(monkeypatch, tmp_path):
    import pytest
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("CANNABLISS_GIT_STATE", raising=False)
    with pytest.raises(RuntimeError, match="durable history"):
        run_cannabliss(_cfg(dry_run=False, cannabliss_state_path=str(tmp_path / "state.json")), _FakeClient())


def test_invalid_rotation_history_aborts_instead_of_inventing_a_baseline(monkeypatch, tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"schema_version": 2, "runs": [], "rotation": null}')
    monkeypatch.setattr("src.main.get_cached_playlist_items", lambda *a, **k: [_item(1)])
    with pytest.raises(ValueError, match="rotation metadata"):
        run_cannabliss(_cfg(cannabliss_state_path=str(path)), _FakeClient())
