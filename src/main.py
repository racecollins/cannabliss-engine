"""Cannabliss automation entrypoint."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import datetime, timezone

from src.cache import get_cached_playlist_items
from src.cannabliss import (
    ListeningSignals,
    active_cooldown_uris,
    append_cannabliss_run,
    build_cannabliss_playlist,
    load_cannabliss_state,
    save_cannabliss_state,
    parse_source_items,
    previous_run_track_uris,
)
from src.preview import write_preview
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
    if (not cfg.dry_run and os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("CANNABLISS_GIT_STATE") != "1"):
        raise RuntimeError("Live Actions runs require durable history wiring; run a preview until it is enabled")
    pending_path = cfg.cannabliss_state_path + ".pending.json"
    if Path(pending_path).exists():
        raise RuntimeError("Unresolved pending update; reconcile Spotify and the saved plan before retrying")
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
    top_track_ranks: dict[str, int] = {}
    if cfg.cannabliss_use_top_tracks:
        print(
            f"\n🎧 Reading your top tracks "
            f"(term={cfg.cannabliss_top_tracks_term}, limit={cfg.cannabliss_top_tracks_limit}) …"
        )
        try:
            if hasattr(client, "get_top_track_ranks"):
                top_track_ranks = client.get_top_track_ranks(
                    time_range=cfg.cannabliss_top_tracks_term, limit=cfg.cannabliss_top_tracks_limit)
                top_track_ids = set(top_track_ranks)
            else:
                top_track_ids = client.get_top_track_ids(
                    time_range=cfg.cannabliss_top_tracks_term, limit=cfg.cannabliss_top_tracks_limit)
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
    if state.get("target_playlist_id", cfg.cannabliss_target_playlist_id) != cfg.cannabliss_target_playlist_id:
        raise ValueError("Saved history belongs to a different target playlist")
    print(f"🧾 Loaded Cannabliss state with {len(state.get('runs', []))} prior runs")

    trusted = state.get("schema_version") == 2
    if trusted and (not isinstance(state.get("rotation"), dict)
                    or not isinstance(state["rotation"].get("tracks"), dict)):
        raise ValueError("Version 2 history has invalid rotation metadata; restore it before continuing")
    previous_uris = previous_run_track_uris(state) if trusted else set()
    rotation = state.get("rotation") if trusted else None
    if not trusted:
        print("🧭 Establishing a fresh baseline; legacy history is not used to infer your edits.")
    target_tracks = parse_source_items(current_items, source_tag="current", current_order=True)
    cooldown_uris = active_cooldown_uris(
        state.get("cooldown", []), now, days=cfg.cannabliss_removal_cooldown_days
    )
    print(
        f"🧊 {len(previous_uris)} tracks in last run; "
        f"{len(cooldown_uris)} benched by cooldown"
    )

    result = build_cannabliss_playlist(
        master_tracks=parse_source_items(master_items, source_tag="master"),
        current_tracks=target_tracks,
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
            top_track_ranks=top_track_ranks,
        ),
        previous_track_uris=previous_uris,
        rotation_state=rotation,
        protection_days=getattr(cfg, "cannabliss_protection_days", 14),
        discovery_per_refresh=getattr(cfg, "cannabliss_discovery_per_refresh", 5),
        removal_cooldown_days=cfg.cannabliss_removal_cooldown_days,
        cooldown_uris=cooldown_uris,
        fresh_front_size=cfg.cannabliss_fresh_front_size,
        fresh_front_max_per_artist=cfg.cannabliss_fresh_front_max_per_artist,
        learn_top_ten=getattr(cfg, "cannabliss_learn_top_ten", False),
        queue_curator_additions=getattr(cfg, "cannabliss_queue_curator_additions", False),
        curator_queue_per_refresh=getattr(cfg, "cannabliss_curator_queue_per_refresh", 10),
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
        "queue_captured",
        "queue_promoted",
        "queued_for_future",
    ):
        values = result.summary.get(label, [])
        preview = ", ".join(values[:10]) if values else "none"
        suffix = " …" if len(values) > 10 else ""
        print(f"  • {label}: {len(values)} ({preview}{suffix})")
    if "total_changed" in result.summary:
        print(f"  • total_changed: {', '.join(result.summary['total_changed'])}")
    if "micro_adjustments" in result.summary:
        print(f"  • micro_adjustments: {', '.join(result.summary['micro_adjustments'])}")

    preview_path = getattr(cfg, "cannabliss_preview_path", "")
    if preview_path:
        write_preview(result, target_tracks, preview_path)
        print(f"📄 Full before/after preview written to {preview_path}")
    if cfg.dry_run:
        print("\n🏜️  DRY RUN — Spotify and saved history are unchanged.")
        return

    uris = [track.uri for track in result.ordered_tracks]
    if not uris:
        raise RuntimeError("Refusing to replace the live playlist with an empty result")
    if os.environ.get("CANNABLISS_EXPECT_NOOP") == "1" and uris != [t.uri for t in target_tracks]:
        raise RuntimeError("Activation verification requires an unchanged playlist; refusing this write")
    print(f"\n✍️  Replacing Cannabliss playlist {cfg.cannabliss_target_playlist_id} …")
    try:
        # Catch edits made while source playlists and listening signals were loading.
        fresh_items = client.get_all_playlist_items(cfg.cannabliss_target_playlist_id)
        if fresh_items != current_items:
            raise RuntimeError("Live playlist changed during planning; rerun the preview")
        git_state = os.environ.get("CANNABLISS_GIT_STATE") == "1"
        pending = {"timestamp": now.isoformat(), "target_playlist_id": cfg.cannabliss_target_playlist_id,
                   "before": [t.uri for t in target_tracks], "after": uris,
                   "proposed_rotation": result.rotation_state}
        if git_state:
            from src.state_store import checkpoint
            checkpoint(cfg.cannabliss_state_path, pending=pending)
        save_cannabliss_state(pending, pending_path)
        client.replace_playlist_tracks(cfg.cannabliss_target_playlist_id, uris)
        actual = parse_source_items(client.get_all_playlist_items(cfg.cannabliss_target_playlist_id),
                                    source_tag="current", current_order=True)
        if [t.uri for t in actual] != uris:
            raise RuntimeError("Spotify readback verification failed; history was not advanced")
    except SpotifyApiError as err:
        _print_spotify_error_help(err)
        sys.exit(1)

    append_cannabliss_run(
        result, path=cfg.cannabliss_state_path, now=now,
        cooldown_days=cfg.cannabliss_removal_cooldown_days,
        target_playlist_id=cfg.cannabliss_target_playlist_id,
    )
    if git_state:
        checkpoint(cfg.cannabliss_state_path)
    Path(pending_path).unlink()
    print(f"🧾 Recorded verified Cannabliss run in {cfg.cannabliss_state_path}")
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
