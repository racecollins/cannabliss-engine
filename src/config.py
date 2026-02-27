"""Configuration: parse and validate environment variables."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    spotify_client_id: str
    spotify_client_secret: str
    spotify_refresh_token: str
    master_playlist_id: str
    fresh_playlist_id: str
    mode: str  # "recent" | "random"
    count: int
    dry_run: bool
    seed: int | None


def load_config() -> Config:
    """Load configuration from environment variables (supports .env via dotenv)."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # dotenv is optional for CI

    return Config(
        spotify_client_id=_require("SPOTIFY_CLIENT_ID"),
        spotify_client_secret=_require("SPOTIFY_CLIENT_SECRET"),
        spotify_refresh_token=_require("SPOTIFY_REFRESH_TOKEN"),
        master_playlist_id=_require("MASTER_PLAYLIST_ID"),
        fresh_playlist_id=_require("FRESH_PLAYLIST_ID"),
        mode=_env("MODE", "random"),
        count=int(_env("COUNT", "100")),
        dry_run=_env("DRY_RUN", "0") == "1",
        seed=int(os.environ["SEED"]) if "SEED" in os.environ else None,
    )


def validate_config(cfg: Config) -> None:
    """Validate config values. Exits with clear error if invalid."""
    errors: list[str] = []

    if cfg.mode not in ("recent", "random"):
        errors.append(f"MODE must be 'recent' or 'random', got '{cfg.mode}'")

    if cfg.count < 1:
        errors.append(f"COUNT must be >= 1, got {cfg.count}")

    if not cfg.master_playlist_id:
        errors.append("MASTER_PLAYLIST_ID is empty")

    if not cfg.fresh_playlist_id:
        errors.append("FRESH_PLAYLIST_ID is empty")

    if cfg.master_playlist_id == cfg.fresh_playlist_id:
        errors.append("MASTER_PLAYLIST_ID and FRESH_PLAYLIST_ID must be different")

    if errors:
        for e in errors:
            print(f"❌ Config error: {e}", file=sys.stderr)
        sys.exit(1)


# ── helpers ──────────────────────────────────────────────────────────

def _require(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        print(f"❌ Missing required env var: {name}", file=sys.stderr)
        sys.exit(1)
    return val


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()
