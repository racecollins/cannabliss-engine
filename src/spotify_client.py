"""Spotify Web API client: auth, reads, writes, retry logic."""

from __future__ import annotations

import time

import requests

TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"

MAX_RETRIES = 3
BACKOFF_BASE = 1.0  # seconds


class SpotifyApiError(RuntimeError):
    """Raised when Spotify returns a non-success API response."""

    def __init__(self, method: str, url: str, status_code: int, message: str) -> None:
        super().__init__(f"Spotify API error {status_code} for {method} {url}: {message}")
        self.method = method
        self.url = url
        self.status_code = status_code
        self.message = message


class SpotifyClient:
    """Thin Spotify API wrapper using refresh-token auth."""

    def __init__(self, client_id: str, client_secret: str, refresh_token: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._access_token: str | None = None
        self._user_id: str | None = None

    # -- Auth -----------------------------------------------------

    def authenticate(self) -> None:
        """Exchange refresh token for a fresh access token."""
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
            },
            auth=(self._client_id, self._client_secret),
            timeout=15,
        )
        if not 200 <= resp.status_code < 300:
            raise SpotifyApiError("POST", TOKEN_URL, resp.status_code, _spotify_error_message(resp))
        data = resp.json()
        self._access_token = data["access_token"]
        print("✅ Authenticated with Spotify")

    # -- Playlist reads ------------------------------------------

    def get_all_playlist_items(self, playlist_id: str) -> list[dict]:
        """Fetch every item from a playlist, handling pagination."""
        items: list[dict] = []
        # Spotify can return 403 on `/tracks` for some playlists where `/items` works.
        # `/items` is the canonical endpoint for playlist content.
        url = f"{API_BASE}/playlists/{playlist_id}/items"
        # Keep params minimal for compatibility: fields filtering differs between
        # `/tracks` and `/items`, and overly strict fields can omit `track`.
        params: dict = {"limit": 100, "offset": 0}

        while url:
            data = self._get(url, params=params)
            for item in data.get("items", []):
                items.append(item)
            url = data.get("next")
            params = {}  # next URL already contains params
            if url:
                print(f"  ... fetched {len(items)} items so far")

        print(f"📥 Fetched {len(items)} total items from playlist {playlist_id}")
        return items

    # -- Playlist writes -----------------------------------------

    def replace_playlist_tracks(self, playlist_id: str, uris: list[str]) -> None:
        """Replace all tracks in a playlist (max 100 per call)."""
        # `/items` works reliably for both read and replace operations.
        url = f"{API_BASE}/playlists/{playlist_id}/items"
        self._put(url, json={"uris": uris})
        print(f"✅ Replaced playlist {playlist_id} with {len(uris)} tracks")

    def create_playlist(self, name: str, description: str, public: bool = False) -> str:
        """Create a playlist for the authenticated user and return its id."""
        if not self._user_id:
            me = self._get(f"{API_BASE}/me")
            self._user_id = me["id"]

        url = f"{API_BASE}/users/{self._user_id}/playlists"
        data = self._post(
            url,
            json={
                "name": name,
                "description": description,
                "public": public,
            },
        )
        playlist_id = data["id"]
        print(f"✅ Created archive playlist {playlist_id}")
        return playlist_id

    def update_playlist_description(self, playlist_id: str, description: str) -> None:
        """Update a playlist's description.

        Spotify can return 403 if the authenticated user can edit tracks but is not allowed
        to change playlist metadata. We treat that case as non-fatal.
        """
        url = f"{API_BASE}/playlists/{playlist_id}"
        try:
            self._put(url, json={"description": description})
        except SpotifyApiError as err:
            if err.status_code == 403:
                print("⚠️  Could not update playlist description (403 Forbidden).")
                print("   Track updates succeeded, but this account cannot edit playlist details.")
                return
            raise
        print("✅ Updated playlist description")

    # -- HTTP helpers with retry ---------------------------------

    def _headers(self) -> dict:
        if not self._access_token:
            raise RuntimeError("Not authenticated - call authenticate() first")
        return {"Authorization": f"Bearer {self._access_token}"}

    def _get(self, url: str, params: dict | None = None) -> dict:
        return self._request("GET", url, params=params)

    def _put(self, url: str, json: dict | None = None) -> dict | None:
        return self._request("PUT", url, json=json)

    def _post(self, url: str, json: dict | None = None) -> dict:
        data = self._request("POST", url, json=json)
        if data is None:
            raise RuntimeError(f"Expected JSON response for POST {url}")
        return data

    def _request(self, method: str, url: str, **kwargs) -> dict | None:
        last_error: SpotifyApiError | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            resp = requests.request(method, url, headers=self._headers(), timeout=30, **kwargs)

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", BACKOFF_BASE * attempt))
                print(
                    f"⏳ Rate limited, retrying in {retry_after}s "
                    f"(attempt {attempt}/{MAX_RETRIES})"
                )
                time.sleep(retry_after)
                continue

            if 200 <= resp.status_code < 300:
                if resp.status_code == 204 or not resp.text:
                    return None
                return resp.json()

            message = _spotify_error_message(resp)
            last_error = SpotifyApiError(method, url, resp.status_code, message)

            # Retry transient 5xx errors; fail fast for 4xx (including 403).
            if 500 <= resp.status_code < 600 and attempt < MAX_RETRIES:
                sleep_for = BACKOFF_BASE * attempt
                print(
                    f"⚠️  Spotify server error {resp.status_code}, retrying in {sleep_for:.1f}s "
                    f"(attempt {attempt}/{MAX_RETRIES})"
                )
                time.sleep(sleep_for)
                continue

            raise last_error

        if last_error is not None:
            raise last_error

        raise RuntimeError(f"Spotify API request failed after {MAX_RETRIES} retries: {method} {url}")


def _spotify_error_message(resp: requests.Response) -> str:
    """Extract the most useful API error message from a Spotify response."""
    try:
        payload = resp.json()
        error = payload.get("error", payload)
        if isinstance(error, dict):
            status = error.get("status")
            message = error.get("message") or str(error)
            return f"status={status}, message={message}" if status else str(message)
        return str(error)
    except ValueError:
        text = resp.text.strip()
        return text or "No response body"
