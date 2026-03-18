# Cannabliss Engine

Cannabliss Engine automates the public Cannabliss Spotify playlist.

It builds a curated 100-song playlist from:
- a read-only Cannabliss Master source
- Hall of Fame context
- optional feeder playlists
- optional personal listening signals from Spotify top tracks and recently played tracks

The playlist is designed to feel alive, intentional, and taste-driven while preserving a stable identity tier at the top.

## Project Docs

- [Cannabliss philosophy](./docs/cannabliss-philosophy.md)
- [Spotify project policy](./docs/spotify-project-policy.md)
- [New Spotify project starter](./docs/new-spotify-project-starter.md)
- [AI engineering guidelines](./AI_ENGINEERING_GUIDELINES.md)

## Setup

### 1. Create a Spotify App

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Open your shared Spotify automation app
3. Ensure this redirect URI is configured:
   - `http://127.0.0.1:8888/callback`
4. Copy your:
   - `SPOTIFY_CLIENT_ID`
   - `SPOTIFY_CLIENT_SECRET`

### 2. Clone and Install

```bash
git clone <your-repo-url> && cd Cannabliss
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment

Create a `.env` file:

```env
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REFRESH_TOKEN=your_refresh_token_here
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
PROFILE=cannabliss
MASTER_PLAYLIST_ID=47W5136lY5XazjWDHmfyxm
CANNABLISS_TARGET_PLAYLIST_ID=3P9XkucRpg9Naz8cGyZOpW
CANNABLISS_HALL_OF_FAME_PLAYLIST_ID=6rdvXMnttC3muaQICqpNmc
CANNABLISS_FEEDER_PLAYLIST_IDS=6rdvXMnttC3muaQICqpNmc
CANNABLISS_TARGET_SIZE=100
CANNABLISS_WEEKLY_INSERTIONS=25
CANNABLISS_UPDATE_MODE=major
CANNABLISS_MICRO_REFRESH_COUNT=5
CANNABLISS_STATE_PATH=data/cannabliss_state.json
CANNABLISS_USE_TOP_TRACKS=0
CANNABLISS_USE_RECENTLY_PLAYED=0
CANNABLISS_TOP_TRACKS_TERM=short_term
CANNABLISS_TOP_TRACKS_LIMIT=50
CANNABLISS_RECENTLY_PLAYED_LIMIT=50
CANNABLISS_TOP_TRACKS_BOOST=0.35
CANNABLISS_RECENTLY_PLAYED_BOOST=0.25
MAX_TRACKS_PER_ARTIST=2
DRY_RUN=0
PLAYLIST_CACHE_DIR=data/cache/playlists
PLAYLIST_CACHE_TTL_HOURS=12
FORCE_REFRESH=0
```

### 4. Get Your Refresh Token

```bash
venv/bin/python3 -m src.refresh_token_helper
```

If you want listening boosts, regenerate your token with scopes that include:
- `user-top-read`
- `user-read-recently-played`

## Usage

### Local Run

```bash
# Major refresh dry run
PROFILE=cannabliss CANNABLISS_UPDATE_MODE=major DRY_RUN=1 venv/bin/python3 -m src.main

# Micro refresh dry run
PROFILE=cannabliss CANNABLISS_UPDATE_MODE=micro DRY_RUN=1 venv/bin/python3 -m src.main

# Dry run with listening boosts
PROFILE=cannabliss CANNABLISS_USE_TOP_TRACKS=1 CANNABLISS_USE_RECENTLY_PLAYED=1 DRY_RUN=1 venv/bin/python3 -m src.main

# Force-refresh playlist sources instead of using cache
FORCE_REFRESH=1 PROFILE=cannabliss DRY_RUN=1 venv/bin/python3 -m src.main

# Live major refresh
PROFILE=cannabliss CANNABLISS_UPDATE_MODE=major DRY_RUN=0 venv/bin/python3 -m src.main
```

### Run Tests

```bash
venv/bin/python3 -m pytest tests/ -q
```

## GitHub Actions

### Required Secrets

In GitHub → Settings → Secrets and variables → Actions:

- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `SPOTIFY_REFRESH_TOKEN`

### Schedule

The workflow runs every Friday at 15:00 UTC.
That maps to 10:00 AM CDT or 9:00 AM CST in America/Chicago.

Scheduled runs force-refresh playlist sources so they use fresh Spotify data.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---:|---|
| `SPOTIFY_CLIENT_ID` | ✅ |  | Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | ✅ |  | Spotify app client secret |
| `SPOTIFY_REFRESH_TOKEN` | ✅ |  | OAuth refresh token |
| `PROFILE` |  | `cannabliss` | Must be `cannabliss` |
| `MASTER_PLAYLIST_ID` | ✅ |  | Read-only Cannabliss master source |
| `CANNABLISS_TARGET_PLAYLIST_ID` | ✅ |  | Public Cannabliss target playlist |
| `CANNABLISS_HALL_OF_FAME_PLAYLIST_ID` |  |  | Hall of Fame source/archive playlist |
| `CANNABLISS_FEEDER_PLAYLIST_IDS` |  |  | Comma-separated feeder playlist IDs |
| `CANNABLISS_TARGET_SIZE` |  | `100` | Cannabliss target size |
| `CANNABLISS_WEEKLY_INSERTIONS` |  | `25` | Major refresh insertion target |
| `CANNABLISS_UPDATE_MODE` |  | `major` | `major` or `micro` |
| `CANNABLISS_MICRO_REFRESH_COUNT` |  | `5` | Change budget for micro refresh |
| `CANNABLISS_STATE_PATH` |  | `data/cannabliss_state.json` | Cannabliss ordered-state log |
| `CANNABLISS_USE_TOP_TRACKS` |  | `0` | `1` enables `/me/top/tracks` boosts |
| `CANNABLISS_USE_RECENTLY_PLAYED` |  | `0` | `1` enables recently-played boosts |
| `CANNABLISS_TOP_TRACKS_TERM` |  | `short_term` | Spotify top-track window |
| `CANNABLISS_TOP_TRACKS_LIMIT` |  | `50` | Max top tracks to read |
| `CANNABLISS_RECENTLY_PLAYED_LIMIT` |  | `50` | Max recently played items to read |
| `CANNABLISS_TOP_TRACKS_BOOST` |  | `0.35` | Premium/current listening boost |
| `CANNABLISS_RECENTLY_PLAYED_BOOST` |  | `0.25` | Recent listening boost |
| `MAX_TRACKS_PER_ARTIST` |  | `2` | Artist cap used during Cannabliss build |
| `DRY_RUN` |  | `0` | `1` previews without Spotify writes |
| `PLAYLIST_CACHE_DIR` |  | `data/cache/playlists` | Local cache directory for playlist reads |
| `PLAYLIST_CACHE_TTL_HOURS` |  | `12` | Cache freshness window in hours |
| `FORCE_REFRESH` |  | `0` | `1` bypasses cache and refetches |

## Safety

- ✅ Cannabliss Master is read-only
- ✅ The public Cannabliss playlist is rewritten from the planned ordered result
- ✅ Playlist description is preserved during Cannabliss updates
- ✅ DRY_RUN mode prevents Spotify writes
- ✅ Secrets stay in env vars / GitHub secrets
- ✅ `.env` is gitignored

## Cannabliss Model

Cannabliss uses a structured playlist shape:
- `1–10`: premium current / identity tier
- `11–25`: high-conviction new arrivals
- `26–40`: discovery tier
- `41–50`: stabilizers / glue
- `51–100`: survivors / long-tail identity

Major refreshes are the main weekly update.
Micro refreshes make small targeted adjustments while keeping the playlist recognizable.
