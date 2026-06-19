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
    profile: str
    master_playlist_id: str
    dry_run: bool
    max_tracks_per_artist: int
    cannabliss_target_playlist_id: str
    cannabliss_hall_of_fame_playlist_id: str
    cannabliss_feeder_playlist_ids: tuple[str, ...]
    cannabliss_target_size: int
    cannabliss_weekly_insertions: int
    cannabliss_update_mode: str
    cannabliss_micro_refresh_count: int
    cannabliss_fresh_front_size: int
    cannabliss_fresh_front_max_per_artist: int
    cannabliss_removal_cooldown_days: int
    cannabliss_state_path: str
    cannabliss_use_top_tracks: bool
    cannabliss_use_recently_played: bool
    cannabliss_top_tracks_term: str
    cannabliss_top_tracks_limit: int
    cannabliss_recently_played_limit: int
    cannabliss_top_tracks_boost: float
    cannabliss_recently_played_boost: float
    playlist_cache_dir: str
    playlist_cache_ttl_hours: int
    force_refresh: bool


def load_config() -> Config:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    return Config(
        spotify_client_id=_require("SPOTIFY_CLIENT_ID"),
        spotify_client_secret=_require("SPOTIFY_CLIENT_SECRET"),
        spotify_refresh_token=_require("SPOTIFY_REFRESH_TOKEN"),
        profile=_env("PROFILE", "cannabliss"),
        master_playlist_id=_env("MASTER_PLAYLIST_ID", ""),
        dry_run=_env("DRY_RUN", "0") == "1",
        max_tracks_per_artist=int(_env("MAX_TRACKS_PER_ARTIST", "2")),
        cannabliss_target_playlist_id=_env("CANNABLISS_TARGET_PLAYLIST_ID", ""),
        cannabliss_hall_of_fame_playlist_id=_env("CANNABLISS_HALL_OF_FAME_PLAYLIST_ID", ""),
        cannabliss_feeder_playlist_ids=tuple(_split_csv(_env("CANNABLISS_FEEDER_PLAYLIST_IDS", ""))),
        cannabliss_target_size=int(_env("CANNABLISS_TARGET_SIZE", "100")),
        cannabliss_weekly_insertions=int(_env("CANNABLISS_WEEKLY_INSERTIONS", "25")),
        cannabliss_update_mode=_env("CANNABLISS_UPDATE_MODE", "major"),
        cannabliss_micro_refresh_count=int(_env("CANNABLISS_MICRO_REFRESH_COUNT", "5")),
        cannabliss_fresh_front_size=int(_env("CANNABLISS_FRESH_FRONT_SIZE", "15")),
        cannabliss_fresh_front_max_per_artist=int(_env("CANNABLISS_FRESH_FRONT_MAX_PER_ARTIST", "2")),
        cannabliss_removal_cooldown_days=int(_env("CANNABLISS_REMOVAL_COOLDOWN_DAYS", "7")),
        cannabliss_state_path=_env("CANNABLISS_STATE_PATH", "data/cannabliss_state.json"),
        cannabliss_use_top_tracks=_env("CANNABLISS_USE_TOP_TRACKS", "0") == "1",
        cannabliss_use_recently_played=_env("CANNABLISS_USE_RECENTLY_PLAYED", "0") == "1",
        cannabliss_top_tracks_term=_env("CANNABLISS_TOP_TRACKS_TERM", "short_term"),
        cannabliss_top_tracks_limit=int(_env("CANNABLISS_TOP_TRACKS_LIMIT", "50")),
        cannabliss_recently_played_limit=int(_env("CANNABLISS_RECENTLY_PLAYED_LIMIT", "50")),
        cannabliss_top_tracks_boost=float(_env("CANNABLISS_TOP_TRACKS_BOOST", "0.35")),
        cannabliss_recently_played_boost=float(_env("CANNABLISS_RECENTLY_PLAYED_BOOST", "0.25")),
        playlist_cache_dir=_env("PLAYLIST_CACHE_DIR", "data/cache/playlists"),
        playlist_cache_ttl_hours=int(_env("PLAYLIST_CACHE_TTL_HOURS", "12")),
        force_refresh=_env("FORCE_REFRESH", "0") == "1",
    )


def validate_config(cfg: Config) -> None:
    errors: list[str] = []

    if cfg.profile != "cannabliss":
        errors.append(f"PROFILE must be 'cannabliss', got '{cfg.profile}'")
    if cfg.max_tracks_per_artist < 1:
        errors.append(f"MAX_TRACKS_PER_ARTIST must be >= 1, got {cfg.max_tracks_per_artist}")
    if cfg.cannabliss_target_size < 1:
        errors.append(f"CANNABLISS_TARGET_SIZE must be >= 1, got {cfg.cannabliss_target_size}")
    if cfg.cannabliss_weekly_insertions < 0:
        errors.append(
            "CANNABLISS_WEEKLY_INSERTIONS must be >= 0, "
            f"got {cfg.cannabliss_weekly_insertions}"
        )
    if cfg.cannabliss_update_mode not in ("major", "micro"):
        errors.append(
            "CANNABLISS_UPDATE_MODE must be 'major' or 'micro', "
            f"got '{cfg.cannabliss_update_mode}'"
        )
    if cfg.cannabliss_micro_refresh_count < 0:
        errors.append(
            "CANNABLISS_MICRO_REFRESH_COUNT must be >= 0, "
            f"got {cfg.cannabliss_micro_refresh_count}"
        )
    if cfg.cannabliss_fresh_front_size < 1:
        errors.append(
            f"CANNABLISS_FRESH_FRONT_SIZE must be >= 1, got {cfg.cannabliss_fresh_front_size}"
        )
    if cfg.cannabliss_fresh_front_max_per_artist < 1:
        errors.append(
            "CANNABLISS_FRESH_FRONT_MAX_PER_ARTIST must be >= 1, "
            f"got {cfg.cannabliss_fresh_front_max_per_artist}"
        )
    if cfg.cannabliss_removal_cooldown_days < 0:
        errors.append(
            "CANNABLISS_REMOVAL_COOLDOWN_DAYS must be >= 0, "
            f"got {cfg.cannabliss_removal_cooldown_days}"
        )
    if cfg.cannabliss_top_tracks_limit < 1:
        errors.append(
            f"CANNABLISS_TOP_TRACKS_LIMIT must be >= 1, got {cfg.cannabliss_top_tracks_limit}"
        )
    if cfg.cannabliss_recently_played_limit < 1:
        errors.append(
            "CANNABLISS_RECENTLY_PLAYED_LIMIT must be >= 1, "
            f"got {cfg.cannabliss_recently_played_limit}"
        )
    if cfg.playlist_cache_ttl_hours < 0:
        errors.append(
            f"PLAYLIST_CACHE_TTL_HOURS must be >= 0, got {cfg.playlist_cache_ttl_hours}"
        )
    for name, value in [
        ("CANNABLISS_TOP_TRACKS_BOOST", cfg.cannabliss_top_tracks_boost),
        ("CANNABLISS_RECENTLY_PLAYED_BOOST", cfg.cannabliss_recently_played_boost),
    ]:
        if value < 0:
            errors.append(f"{name} must be >= 0, got {value}")
    if not cfg.cannabliss_state_path:
        errors.append("CANNABLISS_STATE_PATH must not be empty")
    if not cfg.playlist_cache_dir:
        errors.append("PLAYLIST_CACHE_DIR must not be empty")
    if cfg.cannabliss_top_tracks_term not in ("short_term", "medium_term", "long_term"):
        errors.append(
            "CANNABLISS_TOP_TRACKS_TERM must be one of short_term, medium_term, long_term, "
            f"got '{cfg.cannabliss_top_tracks_term}'"
        )
    if not cfg.master_playlist_id:
        errors.append("MASTER_PLAYLIST_ID is required for PROFILE=cannabliss")
    if not cfg.cannabliss_target_playlist_id:
        errors.append("CANNABLISS_TARGET_PLAYLIST_ID is required for PROFILE=cannabliss")
    if cfg.master_playlist_id and cfg.master_playlist_id == cfg.cannabliss_target_playlist_id:
        errors.append("MASTER_PLAYLIST_ID and CANNABLISS_TARGET_PLAYLIST_ID must be different")
    if (
        cfg.cannabliss_hall_of_fame_playlist_id
        and cfg.cannabliss_hall_of_fame_playlist_id == cfg.cannabliss_target_playlist_id
    ):
        errors.append(
            "CANNABLISS_HALL_OF_FAME_PLAYLIST_ID must be different from "
            "CANNABLISS_TARGET_PLAYLIST_ID"
        )

    if errors:
        for e in errors:
            print(f"❌ Config error: {e}", file=sys.stderr)
        sys.exit(1)


def _require(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        print(f"❌ Missing required env var: {name}", file=sys.stderr)
        sys.exit(1)
    return val


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


def _split_csv(raw: str) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]
