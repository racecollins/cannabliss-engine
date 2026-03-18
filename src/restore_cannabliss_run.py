"""Restore a saved Cannabliss run from data/cannabliss_state.json."""

from __future__ import annotations

import argparse
import json
import os
import sys

from src.spotify_client import SpotifyClient


def main() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(description="Restore a saved Cannabliss run.")
    parser.add_argument(
        "--run-index",
        type=int,
        default=-1,
        help="Run index to restore (1-based). Defaults to latest run.",
    )
    parser.add_argument(
        "--playlist-id",
        default=os.environ.get("CANNABLISS_TARGET_PLAYLIST_ID", "").strip(),
        help="Playlist ID to restore into. Defaults to CANNABLISS_TARGET_PLAYLIST_ID.",
    )
    parser.add_argument(
        "--state-path",
        default=os.environ.get("CANNABLISS_STATE_PATH", "data/cannabliss_state.json"),
        help="Path to Cannabliss state JSON.",
    )
    args = parser.parse_args()

    if not args.playlist_id:
        print("❌ Missing target playlist ID. Set CANNABLISS_TARGET_PLAYLIST_ID or pass --playlist-id.")
        sys.exit(1)

    try:
        with open(args.state_path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except OSError as err:
        print(f"❌ Could not read state file: {err}")
        sys.exit(1)

    runs = payload.get("runs", [])
    if not runs:
        print("❌ No Cannabliss runs found in state file.")
        sys.exit(1)

    if args.run_index == -1:
        run = runs[-1]
        resolved_index = len(runs)
    else:
        if args.run_index < 1 or args.run_index > len(runs):
            print(f"❌ Run index must be between 1 and {len(runs)}")
            sys.exit(1)
        resolved_index = args.run_index
        run = runs[resolved_index - 1]

    track_ids = run.get("track_ids", [])
    if not track_ids:
        print("❌ Selected run has no track IDs.")
        sys.exit(1)

    client = SpotifyClient(
        os.environ.get("SPOTIFY_CLIENT_ID", "").strip(),
        os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip(),
        os.environ.get("SPOTIFY_REFRESH_TOKEN", "").strip(),
    )
    client.authenticate()

    uris = [f"spotify:track:{track_id}" for track_id in track_ids]
    print(
        f"♻️  Restoring Cannabliss run #{resolved_index} "
        f"({run.get('timestamp', 'unknown time')}) with {len(uris)} tracks …"
    )
    client.replace_playlist_tracks(args.playlist_id, uris)
    print("✅ Restore complete")


if __name__ == "__main__":
    main()
