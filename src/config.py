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
    fresh_playlist_id: str
    mode: str  # "recent" | "random"
    count: int
    dry_run: bool
    seed: int | None
    history_weeks: int
    max_tracks_per_artist: int
    fresh_days_1: int
    fresh_days_2: int
    evolve: bool
    candidates: int
    candidate_seed_base: int | None
    score_w_novelty: float
    score_w_diversity: float
    score_w_cohesion: float
    score_w_freshness: float
    evolve_log_path: str
    archive_winner: bool
    cannabliss_target_playlist_id: str
    cannabliss_hall_of_fame_playlist_id: str
    cannabliss_feeder_playlist_ids: tuple[str, ...]
    cannabliss_target_size: int
    cannabliss_weekly_insertions: int
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
        profile=_env("PROFILE", "fresh100"),
        master_playlist_id=_env("MASTER_PLAYLIST_ID", ""),
        fresh_playlist_id=_env("FRESH_PLAYLIST_ID", ""),
        mode=_env("MODE", "random"),
        count=int(_env("COUNT", "100")),
        dry_run=_env("DRY_RUN", "0") == "1",
        seed=_int_optional("SEED"),
        history_weeks=int(_env("HISTORY_WEEKS", "6")),
        max_tracks_per_artist=int(_env("MAX_TRACKS_PER_ARTIST", "2")),
        fresh_days_1=int(_env("FRESH_DAYS_1", "30")),
        fresh_days_2=int(_env("FRESH_DAYS_2", "180")),
        evolve=_env("EVOLVE", "0") == "1",
        candidates=int(_env("CANDIDATES", "7")),
        candidate_seed_base=_int_optional("CANDIDATE_SEED_BASE"),
        score_w_novelty=float(_env("SCORE_W_NOVELTY", "1.0")),
        score_w_diversity=float(_env("SCORE_W_DIVERSITY", "1.0")),
        score_w_cohesion=float(_env("SCORE_W_COHESION", "1.0")),
        score_w_freshness=float(_env("SCORE_W_FRESHNESS", "0.5")),
        evolve_log_path=_env("EVOLVE_LOG_PATH", "data/evolve_log.jsonl"),
        archive_winner=_env("ARCHIVE_WINNER", "0") == "1",
        cannabliss_target_playlist_id=_env("CANNABLISS_TARGET_PLAYLIST_ID", ""),
        cannabliss_hall_of_fame_playlist_id=_env("CANNABLISS_HALL_OF_FAME_PLAYLIST_ID", ""),
        cannabliss_feeder_playlist_ids=tuple(_split_csv(_env("CANNABLISS_FEEDER_PLAYLIST_IDS", ""))),
        cannabliss_target_size=int(_env("CANNABLISS_TARGET_SIZE", "160")),
        cannabliss_weekly_insertions=int(_env("CANNABLISS_WEEKLY_INSERTIONS", "40")),
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
    """Validate config values. Exits with clear error if invalid."""
    errors: list[str] = []

    if cfg.profile not in ("fresh100", "cannabliss"):
        errors.append(f"PROFILE must be 'fresh100' or 'cannabliss', got '{cfg.profile}'")

    if cfg.mode not in ("recent", "random"):
        errors.append(f"MODE must be 'recent' or 'random', got '{cfg.mode}'")

    if cfg.count < 1:
        errors.append(f"COUNT must be >= 1, got {cfg.count}")
    if cfg.history_weeks < 0:
        errors.append(f"HISTORY_WEEKS must be >= 0, got {cfg.history_weeks}")
    if cfg.max_tracks_per_artist < 1:
        errors.append(f"MAX_TRACKS_PER_ARTIST must be >= 1, got {cfg.max_tracks_per_artist}")
    if cfg.fresh_days_1 < 1:
        errors.append(f"FRESH_DAYS_1 must be >= 1, got {cfg.fresh_days_1}")
    if cfg.fresh_days_2 < cfg.fresh_days_1:
        errors.append(
            f"FRESH_DAYS_2 must be >= FRESH_DAYS_1 ({cfg.fresh_days_1}), got {cfg.fresh_days_2}"
        )
    if cfg.candidates < 1:
        errors.append(f"CANDIDATES must be >= 1, got {cfg.candidates}")
    if cfg.cannabliss_target_size < 1:
        errors.append(f"CANNABLISS_TARGET_SIZE must be >= 1, got {cfg.cannabliss_target_size}")
    if cfg.cannabliss_weekly_insertions < 0:
        errors.append(
            "CANNABLISS_WEEKLY_INSERTIONS must be >= 0, "
            f"got {cfg.cannabliss_weekly_insertions}"
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
        ("SCORE_W_NOVELTY", cfg.score_w_novelty),
        ("SCORE_W_DIVERSITY", cfg.score_w_diversity),
        ("SCORE_W_COHESION", cfg.score_w_cohesion),
        ("SCORE_W_FRESHNESS", cfg.score_w_freshness),
        ("CANNABLISS_TOP_TRACKS_BOOST", cfg.cannabliss_top_tracks_boost),
        ("CANNABLISS_RECENTLY_PLAYED_BOOST", cfg.cannabliss_recently_played_boost),
    ]:
        if value < 0:
            errors.append(f"{name} must be >= 0, got {value}")
    if not cfg.evolve_log_path:
        errors.append("EVOLVE_LOG_PATH must not be empty")
    if not cfg.cannabliss_state_path:
        errors.append("CANNABLISS_STATE_PATH must not be empty")
    if not cfg.playlist_cache_dir:
        errors.append("PLAYLIST_CACHE_DIR must not be empty")
    if cfg.cannabliss_top_tracks_term not in ("short_term", "medium_term", "long_term"):
        errors.append(
            "CANNABLISS_TOP_TRACKS_TERM must be one of short_term, medium_term, long_term, "
            f"got '{cfg.cannabliss_top_tracks_term}'"
        )

    if cfg.profile == "fresh100":
        if not cfg.master_playlist_id:
            errors.append("MASTER_PLAYLIST_ID is empty")
        if not cfg.fresh_playlist_id:
            errors.append("FRESH_PLAYLIST_ID is empty")
        if cfg.master_playlist_id and cfg.master_playlist_id == cfg.fresh_playlist_id:
            errors.append("MASTER_PLAYLIST_ID and FRESH_PLAYLIST_ID must be different")
    else:
        if not cfg.master_playlist_id:
            errors.append("MASTER_PLAYLIST_ID is required for PROFILE=cannabliss")
        if not cfg.cannabliss_target_playlist_id:
            errors.append("CANNABLISS_TARGET_PLAYLIST_ID is required for PROFILE=cannabliss")
        if cfg.master_playlist_id and cfg.master_playlist_id == cfg.cannabliss_target_playlist_id:
            errors.append(
                "MASTER_PLAYLIST_ID and CANNABLISS_TARGET_PLAYLIST_ID must be different"
            )
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


# ── helpers ──────────────────────────────────────────────────────────

def _require(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        print(f"❌ Missing required env var: {name}", file=sys.stderr)
        sys.exit(1)
    return val


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


def _int_optional(name: str) -> int | None:
    val = os.environ.get(name, "").strip()
    if not val:
        return None
    return int(val)


def _split_csv(raw: str) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]
