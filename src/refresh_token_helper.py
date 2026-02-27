"""One-time helper: obtain a Spotify refresh token via OAuth Authorization Code flow.

Usage:
    python -m src.refresh_token_helper

Requires env vars: SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
Uses a local loopback callback server.
"""

from __future__ import annotations

import os
import ssl
import subprocess
import sys
import tempfile
import urllib.parse
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests

SCOPES = "playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8888/callback"


def _generate_self_signed_cert(cert_path: str, key_path: str) -> None:
    """Generate a temporary self-signed certificate using openssl."""
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", key_path,
            "-out", cert_path,
            "-days", "1",
            "-nodes",
            "-subj", "/CN=localhost",
        ],
        check=True,
        capture_output=True,
    )


def main() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
    redirect_uri = os.environ.get("SPOTIFY_REDIRECT_URI", DEFAULT_REDIRECT_URI).strip()

    if not client_id or not client_secret:
        print("❌ Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET env vars first.")
        sys.exit(1)

    # ── Step 1: Open browser for user auth ────────────────────────
    params = urllib.parse.urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
    })
    auth_url = f"{AUTH_URL}?{params}"

    print("🌐 Opening browser for Spotify authorization …")
    print(f"   If it doesn't open, visit:\n   {auth_url}\n")
    webbrowser.open(auth_url)

    # ── Step 2: Local callback server to capture the callback ─────
    parsed = urllib.parse.urlparse(redirect_uri)
    port = parsed.port or 8888
    scheme = (parsed.scheme or "http").lower()
    if scheme not in ("http", "https"):
        print("❌ SPOTIFY_REDIRECT_URI must use http or https.")
        sys.exit(1)
    auth_code: str | None = None

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            auth_code = qs.get("code", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            if auth_code:
                self.wfile.write(b"<h1>&#9989; Success! You can close this tab.</h1>")
            else:
                error = qs.get("error", ["unknown"])[0]
                self.wfile.write(f"<h1>&#10060; Error: {error}</h1>".encode())

        def log_message(self, format, *args):
            pass  # suppress noisy HTTP logs

    server = HTTPServer(("127.0.0.1", port), CallbackHandler)
    if scheme == "https":
        with tempfile.TemporaryDirectory() as tmp:
            cert_path = os.path.join(tmp, "cert.pem")
            key_path = os.path.join(tmp, "key.pem")

            print("🔐 Generating temporary self-signed certificate …")
            try:
                _generate_self_signed_cert(cert_path, key_path)
            except (subprocess.CalledProcessError, FileNotFoundError):
                print("❌ Could not generate certificate. Make sure 'openssl' is installed.")
                print("   macOS: comes pre-installed")
                print("   Linux: sudo apt install openssl")
                print("   Windows: install Git Bash or OpenSSL for Windows")
                sys.exit(1)

            ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_ctx.load_cert_chain(cert_path, key_path)
            server.socket = ssl_ctx.wrap_socket(server.socket, server_side=True)

            print(f"⏳ Waiting for callback on https://127.0.0.1:{port} …")
            print("   ⚠️  Your browser will show a security warning — this is expected.")
            print('   Click "Advanced" → "Proceed to localhost" to continue.\n')
            server.handle_request()
    else:
        print(f"⏳ Waiting for callback on http://127.0.0.1:{port} …\n")
        server.handle_request()

    if not auth_code:
        print("❌ No authorization code received.")
        sys.exit(1)

    # ── Step 3: Exchange code for tokens ──────────────────────────
    print("🔑 Exchanging code for tokens …")
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": redirect_uri,
        },
        auth=(client_id, client_secret),
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    refresh_token = data.get("refresh_token")
    if not refresh_token:
        print("❌ No refresh token in response. Try again.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✅ REFRESH TOKEN (save this securely!):")
    print(f"\n   {refresh_token}\n")
    print("=" * 60)
    print("\nAdd it to your .env file as:")
    print(f'   SPOTIFY_REFRESH_TOKEN={refresh_token}')
    print("\nOr add it as a GitHub Actions secret named SPOTIFY_REFRESH_TOKEN")


if __name__ == "__main__":
    main()
