"""Tests for Spotify client helper behavior that doesn't require live API calls."""

import requests
from src.spotify_client import API_BASE, SpotifyClient


def test_replace_playlist_tracks_chunks_over_100(monkeypatch):
    client = SpotifyClient("id", "secret", "refresh")
    calls: list[tuple[str, str, list[str]]] = []

    def fake_put(url: str, json: dict | None = None):
        calls.append(("PUT", url, (json or {}).get("uris", [])))
        return None

    def fake_post(url: str, json: dict | None = None):
        calls.append(("POST", url, (json or {}).get("uris", [])))
        return {"snapshot_id": "snap"}

    monkeypatch.setattr(client, "_put", fake_put)
    monkeypatch.setattr(client, "_post", fake_post)

    uris = [f"spotify:track:{i}" for i in range(160)]
    client.replace_playlist_tracks("playlist123", uris)

    assert len(calls) == 2
    assert calls[0][0] == "PUT"
    assert calls[0][1] == f"{API_BASE}/playlists/playlist123/items"
    assert len(calls[0][2]) == 100
    assert calls[1][0] == "POST"
    assert calls[1][1] == f"{API_BASE}/playlists/playlist123/items"
    assert len(calls[1][2]) == 60


def test_replace_playlist_tracks_handles_empty_playlist(monkeypatch):
    client = SpotifyClient("id", "secret", "refresh")
    calls: list[tuple[str, list[str]]] = []

    def fake_put(url: str, json: dict | None = None):
        calls.append((url, (json or {}).get("uris", [])))
        return None

    monkeypatch.setattr(client, "_put", fake_put)

    client.replace_playlist_tracks("playlist123", [])

    assert len(calls) == 1
    assert calls[0][0] == f"{API_BASE}/playlists/playlist123/items"
    assert calls[0][1] == []


def test_request_caps_retry_after_header(monkeypatch):
    client = SpotifyClient("id", "secret", "refresh")
    client._access_token = "token"
    sleeps: list[int] = []
    calls = {"count": 0}

    class FakeResponse:
        def __init__(self, status_code, headers=None, json_payload=None, text=""):
            self.status_code = status_code
            self.headers = headers or {}
            self._json_payload = json_payload or {}
            self.text = text

        def json(self):
            return self._json_payload

    def fake_request(method, url, headers=None, timeout=30, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return FakeResponse(429, headers={"Retry-After": "79576"})
        return FakeResponse(200, json_payload={"ok": True}, text='{"ok": true}')

    monkeypatch.setattr(requests, "request", fake_request)
    monkeypatch.setattr("src.spotify_client.time.sleep", lambda seconds: sleeps.append(seconds))

    out = client._request("GET", f"{API_BASE}/test")

    assert out == {"ok": True}
    assert sleeps == [60]
