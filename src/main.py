"""Fresh 100 — main entrypoint."""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from src.config import load_config, validate_config
from src.spotify_client import SpotifyApiError, SpotifyClient
from src.selection import append_history, load_history, parse_tracks, select_tracks_from_tracks


def main() -> None:
    # ── Config ────────────────────────────────────────────────────
    cfg = load_config()
    validate_config(cfg)

    print(f"🎵 Fresh 100 — mode={cfg.mode}, count={cfg.count}, dry_run={cfg.dry_run}")
    if cfg.seed is not None:
        print(f"🎲 Seed: {cfg.seed}")
    print(
        f"🧠 HISTORY_WEEKS={cfg.history_weeks}, MAX_TRACKS_PER_ARTIST={cfg.max_tracks_per_artist}, "
        f"FRESH_DAYS_1={cfg.fresh_days_1}, FRESH_DAYS_2={cfg.fresh_days_2}"
    )

    # ── Auth ──────────────────────────────────────────────────────
    client = SpotifyClient(cfg.spotify_client_id, cfg.spotify_client_secret, cfg.spotify_refresh_token)
    try:
        client.authenticate()
    except SpotifyApiError as err:
        _print_spotify_error_help(err)
        sys.exit(1)

    # ── Read Master ───────────────────────────────────────────────
    print(f"\n📖 Reading Master playlist {cfg.master_playlist_id} …")
    try:
        raw_items = client.get_all_playlist_items(cfg.master_playlist_id)
    except SpotifyApiError as err:
        _print_spotify_error_help(err)
        sys.exit(1)

    if not raw_items:
        print("⚠️  Master playlist is empty. Nothing to do.")
        sys.exit(0)

    # ── Select ────────────────────────────────────────────────────
    print(f"\n🔀 Selecting {cfg.count} tracks (mode={cfg.mode}) …")
    parsed = parse_tracks(raw_items)
    print(f"📋 Parsed {len(parsed)} valid tracks")
    history_runs = load_history()
    selected, _meta = select_tracks_from_tracks(
        parsed,
        mode=cfg.mode,
        count=cfg.count,
        seed=cfg.seed,
        history_runs=history_runs,
        history_weeks=cfg.history_weeks,
        max_tracks_per_artist=cfg.max_tracks_per_artist,
        fresh_days_1=cfg.fresh_days_1,
        fresh_days_2=cfg.fresh_days_2,
    )

    if not selected:
        print("⚠️  No valid tracks found after filtering. Nothing to do.")
        sys.exit(0)

    # ── Print selection ───────────────────────────────────────────
    print(f"\n🎶 Selected {len(selected)} tracks:")
    for i, t in enumerate(selected, 1):
        print(f"  {i:>3}. {t.name} — {t.artists}")

    # ── Write or dry-run ──────────────────────────────────────────
    if cfg.dry_run:
        append_history(selected, cfg.mode, cfg.seed)
        print("🧾 Recorded run in data/history.json")
        print("\n🏜️  DRY RUN — no changes made to Spotify.")
        return

    uris = [t.uri for t in selected]
    print(f"\n✍️  Replacing Fresh 100 playlist {cfg.fresh_playlist_id} …")
    try:
        client.replace_playlist_tracks(cfg.fresh_playlist_id, uris)
    except SpotifyApiError as err:
        _print_spotify_error_help(err)
        sys.exit(1)

    # ── Update description ────────────────────────────────────────
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    desc = f"Auto-updated {now} · Mode: {cfg.mode} · {len(selected)} tracks from Master"
    client.update_playlist_description(cfg.fresh_playlist_id, desc)
    append_history(selected, cfg.mode, cfg.seed)
    print("🧾 Recorded run in data/history.json")

    print("\n🎉 Done!")


def _print_spotify_error_help(err: SpotifyApiError) -> None:
    print(f"\n❌ {err}", file=sys.stderr)
    if err.status_code != 403:
        return

    print("Spotify returned 403 Forbidden. Common fixes:", file=sys.stderr)
    print(
        "  1) Regenerate SPOTIFY_REFRESH_TOKEN with `python -m src.refresh_token_helper` "
        "to ensure required scopes are granted.",
        file=sys.stderr,
    )
    print(
        "  2) Confirm the same Spotify account owns (or has edit access to) "
        "FRESH_PLAYLIST_ID.",
        file=sys.stderr,
    )
    print(
        "  3) If MASTER_PLAYLIST_ID is collaborative/private, ensure that account can "
        "view it.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
