"""Cannabliss automation entrypoint."""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from src.cache import get_cached_playlist_items
from src.cannabliss import (
    ListeningSignals,
    active_cooldown_uris,
    append_cannabliss_run,
    build_cannabliss_playlist,
    load_cannabliss_state,
    parse_source_items,
    previous_run_track_uris,
)
from src.config import load_config, validate_config
from src.spotify_client import SpotifyApiError, SpotifyAuthError, SpotifyClient


def main() -> None:
    cfg = load_config()
    validate_config(cfg)

    print(
        f"🎵 Cannabliss automation — profile={cfg.profile}, "
        f"dry_run={cfg.dry_run}"
    )

    client = SpotifyClient(
        cfg.spotify_client_id,
        cfg.spotify_client_secret,
        cfg.spotify_refresh_token,
    )
    try:
        client.authenticate()
    except SpotifyApiError as err:
        _print_spotify_error_help(err)
        sys.exit(1)

    run_cannabliss(cfg, client)


def run_cannabliss(cfg, client: SpotifyClient) -> None:
    print(
        f"🌿 Cannabliss — target_size={cfg.cannabliss_target_size}, "
        f"update_mode={cfg.cannabliss_update_mode}, "
        f"weekly_insertions={cfg.cannabliss_weekly_insertions}, "
        f"micro_refresh_count={cfg.cannabliss_micro_refresh_count}"
    )
    print(f"🛡️  Master {cfg.master_playlist_id} is read-only in this profile.")

    print(f"\n📖 Reading Cannabliss Master playlist {cfg.master_playlist_id} …")
    try:
        master_items = get_cached_playlist_items(
            client,
            cfg.master_playlist_id,
            cache_dir=cfg.playlist_cache_dir,
            ttl_hours=cfg.playlist_cache_ttl_hours,
            force_refresh=cfg.force_refresh,
        )
        current_items = get_cached_playlist_items(
            client,
            cfg.cannabliss_target_playlist_id,
            cache_dir=cfg.playlist_cache_dir,
            ttl_hours=cfg.playlist_cache_ttl_hours,
            force_refresh=True,
        )
        hall_items = (
            get_cached_playlist_items(
                client,
                cfg.cannabliss_hall_of_fame_playlist_id,
                cache_dir=cfg.playlist_cache_dir,
                ttl_hours=cfg.playlist_cache_ttl_hours,
                force_refresh=cfg.force_refresh,
            )
            if cfg.cannabliss_hall_of_fame_playlist_id
            else []
        )
    except SpotifyApiError as err:
        _print_spotify_error_help(err)
        sys.exit(1)

    feeder_tracks = []
    for playlist_id in cfg.cannabliss_feeder_playlist_ids:
        print(f"\n📡 Reading feeder playlist {playlist_id} …")
        try:
            feeder_items = get_cached_playlist_items(
                client,
                playlist_id,
                cache_dir=cfg.playlist_cache_dir,
                ttl_hours=cfg.playlist_cache_ttl_hours,
                force_refresh=cfg.force_refresh,
            )
        except SpotifyApiError as err:
            print(f"⚠️  Skipping feeder playlist {playlist_id}: {err}")
            continue
        feeder_tracks.extend(parse_source_items(feeder_items, source_tag=f"feeder:{playlist_id}"))

    top_track_ids: set[str] = set()
    if cfg.cannabliss_use_top_tracks:
        print(
            f"\n🎧 Reading your top tracks "
            f"(term={cfg.cannabliss_top_tracks_term}, limit={cfg.cannabliss_top_tracks_limit}) …"
        )
        try:
            top_track_ids = client.get_top_track_ids(
                time_range=cfg.cannabliss_top_tracks_term,
                limit=cfg.cannabliss_top_tracks_limit,
            )
            print(f"✅ Loaded {len(top_track_ids)} top-track IDs")
        except SpotifyApiError as err:
            print(f"⚠️  Could not load top tracks: {err}")
            print("   Continuing without top-track listening boosts.")

    recently_played_ids: set[str] = set()
    if cfg.cannabliss_use_recently_played:
        print(
            f"\n🕒 Reading your recently played tracks "
            f"(limit={cfg.cannabliss_recently_played_limit}) …"
        )
        try:
            recently_played_ids = client.get_recently_played_track_ids(
                limit=cfg.cannabliss_recently_played_limit,
            )
            print(f"✅ Loaded {len(recently_played_ids)} recently-played track IDs")
        except SpotifyApiError as err:
            print(f"⚠️  Could not load recently played tracks: {err}")
            print("   Continuing without recent-listening boosts.")

    now = datetime.now(timezone.utc)
    state = load_cannabliss_state(cfg.cannabliss_state_path)
    print(f"🧾 Loaded Cannabliss state with {len(state.get('runs', []))} prior runs")

    previous_uris = previous_run_track_uris(state)
    cooldown_uris = active_cooldown_uris(
        state.get("cooldown", []), now, days=cfg.cannabliss_removal_cooldown_days
    )
    print(
        f"🧊 {len(previous_uris)} tracks in last run; "
        f"{len(cooldown_uris)} benched by cooldown"
    )

    result = build_cannabliss_playlist(
        master_tracks=parse_source_items(master_items, source_tag="master"),
        current_tracks=parse_source_items(current_items, source_tag="current", current_order=True),
        feeder_tracks=feeder_tracks,
        hall_tracks=parse_source_items(hall_items, source_tag="hall"),
        target_size=cfg.cannabliss_target_size,
        weekly_insertions=cfg.cannabliss_weekly_insertions,
        update_mode=cfg.cannabliss_update_mode,
        micro_refresh_count=cfg.cannabliss_micro_refresh_count,
        max_tracks_per_artist=cfg.max_tracks_per_artist,
        listening_signals=ListeningSignals(
            top_track_ids=frozenset(top_track_ids),
            recently_played_ids=frozenset(recently_played_ids),
            top_tracks_boost=cfg.cannabliss_top_tracks_boost,
            recently_played_boost=cfg.cannabliss_recently_played_boost,
        ),
        previous_track_uris=previous_uris,
        cooldown_uris=cooldown_uris,
        fresh_front_size=cfg.cannabliss_fresh_front_size,
        fresh_front_max_per_artist=cfg.cannabliss_fresh_front_max_per_artist,
        now=now,
    )

    print(
        f"\n🎛️  Cannabliss {result.update_mode} refresh preview "
        f"({len(result.ordered_tracks)} total tracks):"
    )
    for i, track in enumerate(result.ordered_tracks[:50], start=1):
        print(f"  {i:>3}. {track.name} — {track.artists}")

    print("\n📦 Cannabliss changes:")
    for label in (
        "added",
        "promoted",
        "held",
        "shifted_down",
        "removed",
        "fresh_front_added",
    ):
        values = result.summary.get(label, [])
        preview = ", ".join(values[:10]) if values else "none"
        suffix = " …" if len(values) > 10 else ""
        print(f"  • {label}: {len(values)} ({preview}{suffix})")
    if "total_changed" in result.summary:
        print(f"  • total_changed: {', '.join(result.summary['total_changed'])}")
    if "micro_adjustments" in result.summary:
        print(f"  • micro_adjustments: {', '.join(result.summary['micro_adjustments'])}")

    append_cannabliss_run(
        result,
        path=cfg.cannabliss_state_path,
        now=now,
        cooldown_days=cfg.cannabliss_removal_cooldown_days,
    )
    print(f"🧾 Recorded Cannabliss run in {cfg.cannabliss_state_path}")

    if cfg.dry_run:
        print("\n🏜️  DRY RUN — no changes made to Spotify.")
        return

    uris = [track.uri for track in result.ordered_tracks]
    print(f"\n✍️  Replacing Cannabliss playlist {cfg.cannabliss_target_playlist_id} …")
    try:
        client.replace_playlist_tracks(cfg.cannabliss_target_playlist_id, uris)
    except SpotifyApiError as err:
        _print_spotify_error_help(err)
        sys.exit(1)

    print("\n🎉 Cannabliss update complete!")


def _print_spotify_error_help(err: SpotifyApiError) -> None:
    print(f"\n❌ {err}", file=sys.stderr)

    if isinstance(err, SpotifyAuthError):
        print(err.remediation, file=sys.stderr)
        return

    if err.status_code != 403:
        return

    print("Spotify returned 403 Forbidden. Common fixes:", file=sys.stderr)
    print(
        "  1) Regenerate SPOTIFY_REFRESH_TOKEN with `venv/bin/python3 -m src.refresh_token_helper` "
        "to ensure required scopes are granted.",
        file=sys.stderr,
    )
    print(
        "  2) Confirm the same Spotify account owns (or has edit access to) "
        "CANNABLISS_TARGET_PLAYLIST_ID.",
        file=sys.stderr,
    )
    print(
        "  3) If MASTER_PLAYLIST_ID is collaborative/private, ensure that account can "
        "view it.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
