# 🎵 Spotify Playlist Automation

Automated Spotify playlist curator with two profiles:

- `fresh100`: maintains a Fresh 100 playlist from your large Master playlist
- `cannabliss`: builds a curated 100-song Cannabliss playlist from a read-only Master source, Hall of Fame, and feeder playlists

## How It Works

1. Reads all tracks from your Master playlist (~3000 songs)
2. Filters out podcasts, episodes, local files, and duplicates
3. Selects 100 tracks (random or most recent)
4. Replaces your Fresh 100 playlist with the selection
5. Updates the playlist description with run metadata

Runs locally or automatically via GitHub Actions every Friday.

---

## Project Docs

- [Cannabliss philosophy](./docs/cannabliss-philosophy.md)
- [Spotify project policy](./docs/spotify-project-policy.md)
- [New Spotify project starter](./docs/new-spotify-project-starter.md)

---

## Setup

### 1. Create a Spotify App

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Click **Create App**
3. Fill in:
   - **App name**: Fresh 100
   - **Redirect URI**: `http://127.0.0.1:8888/callback`
   - **APIs used**: Web API
4. Save and note your **Client ID** and **Client Secret**

### 2. Clone & Install

```bash
git clone <your-repo-url> && cd Cannabliss
pip install -r requirements.txt
```

### 3. Configure Environment

Create a `.env` file:

```env
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
PROFILE=fresh100
MASTER_PLAYLIST_ID=3P9XkucRpg9Naz8cGyZOpW
FRESH_PLAYLIST_ID=1h9wSgaNgFMTvt73qrgccn
MODE=random
COUNT=100
DRY_RUN=0
HISTORY_WEEKS=6
MAX_TRACKS_PER_ARTIST=2
FRESH_DAYS_1=30
FRESH_DAYS_2=180
EVOLVE=0
CANDIDATES=7
SCORE_W_NOVELTY=1.0
SCORE_W_DIVERSITY=1.0
SCORE_W_COHESION=1.0
SCORE_W_FRESHNESS=0.5
EVOLVE_LOG_PATH=data/evolve_log.jsonl
ARCHIVE_WINNER=0
```

For Cannabliss, add:

```env
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
PLAYLIST_CACHE_DIR=data/cache/playlists
PLAYLIST_CACHE_TTL_HOURS=12
FORCE_REFRESH=0
```

### 4. Get Your Refresh Token (One Time)

```bash
python -m src.refresh_token_helper
```

This opens your browser for Spotify login and returns to a local callback URL. You'll get a refresh token. Add it to `.env`:

```env
SPOTIFY_REFRESH_TOKEN=your_refresh_token_here
```

If you previously generated a token before collaborative playlist support was added, regenerate it with the helper above to avoid `403 Forbidden` on collaborative playlists.

---

## Usage

### Local Run

```bash
# Dry run — see which tracks would be selected, no Spotify changes
DRY_RUN=1 python -m src.main

# Live run — replace Fresh 100 playlist
python -m src.main

# Recent mode instead of random
MODE=recent python -m src.main

# Reproducible random selection
SEED=42 python -m src.main

# Evolution mode dry run (generate/score candidates, no Spotify writes)
EVOLVE=1 CANDIDATES=7 DRY_RUN=1 python -m src.main

# Cannabliss major refresh dry run (build curated ordered playlist, no Spotify writes)
PROFILE=cannabliss DRY_RUN=1 python -m src.main

# Cannabliss dry run with your Spotify listening boosts
PROFILE=cannabliss CANNABLISS_USE_TOP_TRACKS=1 CANNABLISS_USE_RECENTLY_PLAYED=1 DRY_RUN=1 python -m src.main

# Cannabliss micro refresh dry run
PROFILE=cannabliss CANNABLISS_UPDATE_MODE=micro DRY_RUN=1 python -m src.main

# Force-refresh playlist sources instead of using cache
FORCE_REFRESH=1 PROFILE=cannabliss DRY_RUN=1 python -m src.main
```

### Smoke Test

```bash
DRY_RUN=1 python -m src.main
```

You should see 100 track names printed without any Spotify writes.

### Run Tests

```bash
python -m pytest tests/ -v
```

---

## GitHub Actions (Weekly Cron)

### Add Secrets

In your repo → **Settings → Secrets and variables → Actions**, add:

| Secret                    | Value                    |
|---------------------------|--------------------------|
| `SPOTIFY_CLIENT_ID`       | Your Spotify Client ID   |
| `SPOTIFY_CLIENT_SECRET`   | Your Spotify Client Secret |
| `SPOTIFY_REFRESH_TOKEN`   | Your refresh token       |

### Schedule

The workflow runs **every Friday at 15:00 UTC** automatically. That maps to **10:00 AM CDT** or **9:00 AM CST** in America/Chicago. Scheduled runs force-refresh playlist sources so they always use fresh Spotify data.

### Manual Trigger

Go to **Actions → Cannabliss Weekly Update → Run workflow** and choose your options.

---

## Environment Variables

| Variable                 | Required | Default    | Description                              |
|--------------------------|----------|------------|------------------------------------------|
| `SPOTIFY_CLIENT_ID`      | ✅       |            | Spotify app client ID                    |
| `SPOTIFY_CLIENT_SECRET`  | ✅       |            | Spotify app client secret                |
| `SPOTIFY_REFRESH_TOKEN`  | ✅       |            | OAuth refresh token                      |
| `PROFILE`                |          | `fresh100` | `fresh100` or `cannabliss`               |
| `MASTER_PLAYLIST_ID`     | ✅       |            | Source playlist ID                       |
| `FRESH_PLAYLIST_ID`      |          |            | Destination playlist ID for Fresh 100    |
| `MODE`                   |          | `random`   | `random` or `recent`                     |
| `COUNT`                  |          | `100`      | Number of tracks to select               |
| `DRY_RUN`                |          | `0`        | `1` to preview without Spotify writes    |
| `SEED`                   |          |            | Random seed for reproducible selection   |
| `HISTORY_WEEKS`          |          | `6`        | Exclude tracks from last N runs          |
| `MAX_TRACKS_PER_ARTIST`  |          | `2`        | Artist cap per selection                 |
| `FRESH_DAYS_1`           |          | `30`       | Recent-tier days (weight 3 in random)    |
| `FRESH_DAYS_2`           |          | `180`      | Mid-tier days (weight 2 in random)       |
| `EVOLVE`                 |          | `0`        | `1` enables evolutionary candidate scoring |
| `CANDIDATES`             |          | `7`        | Number of candidates to generate          |
| `CANDIDATE_SEED_BASE`    |          |            | Stable base seed for deterministic candidates |
| `SCORE_W_NOVELTY`        |          | `1.0`      | Novelty weight in evolution score         |
| `SCORE_W_DIVERSITY`      |          | `1.0`      | Diversity weight in evolution score       |
| `SCORE_W_COHESION`       |          | `1.0`      | Cohesion weight in evolution score        |
| `SCORE_W_FRESHNESS`      |          | `0.5`      | Freshness weight in evolution score       |
| `EVOLVE_LOG_PATH`        |          | `data/evolve_log.jsonl` | JSONL run log for candidates/winner |
| `ARCHIVE_WINNER`         |          | `0`        | `1` creates dated winner archive playlist |
| `CANNABLISS_TARGET_PLAYLIST_ID` |          |            | Destination playlist ID for Cannabliss |
| `CANNABLISS_HALL_OF_FAME_PLAYLIST_ID` |          |        | Hall of Fame source/archive playlist |
| `CANNABLISS_FEEDER_PLAYLIST_IDS` |          |            | Comma-separated feeder playlist IDs |
| `CANNABLISS_TARGET_SIZE` |          | `100`      | Cannabliss target size                   |
| `CANNABLISS_WEEKLY_INSERTIONS` |          | `25`   | Major refresh insertion target |
| `CANNABLISS_UPDATE_MODE` |          | `major`    | `major` or `micro` Cannabliss refresh mode |
| `CANNABLISS_MICRO_REFRESH_COUNT` |       | `5`      | Small-change budget for micro refreshes |
| `CANNABLISS_STATE_PATH`  |          | `data/cannabliss_state.json` | Cannabliss ordered-state log |
| `CANNABLISS_USE_TOP_TRACKS` |      | `0`        | `1` enables `/me/top/tracks` boosts      |
| `CANNABLISS_USE_RECENTLY_PLAYED` | | `0`      | `1` enables recently-played boosts       |
| `CANNABLISS_TOP_TRACKS_TERM` |    | `short_term` | Spotify top-track window               |
| `CANNABLISS_TOP_TRACKS_LIMIT` |   | `50`       | Max top tracks to read                   |
| `CANNABLISS_RECENTLY_PLAYED_LIMIT` | | `50`    | Max recently played items to read        |
| `CANNABLISS_TOP_TRACKS_BOOST` |   | `0.35`     | Premium/current listening boost          |
| `CANNABLISS_RECENTLY_PLAYED_BOOST` | | `0.25`  | Recent listening boost                   |
| `PLAYLIST_CACHE_DIR`      |          | `data/cache/playlists` | Local cache directory for playlist reads |
| `PLAYLIST_CACHE_TTL_HOURS` |         | `12`       | Cache freshness window in hours          |
| `FORCE_REFRESH`           |          | `0`        | `1` bypasses playlist cache and refetches |

---

## Safety

- ✅ Master playlist is **never modified** — only read
- ✅ Fresh 100 is **replaced entirely** each run — no bloat
- ✅ Cannabliss Master is **read-only by construction**
- ✅ No secrets in code — all via env vars / GitHub Secrets
- ✅ DRY_RUN mode for safe previews
- ✅ `.env` is gitignored

## Cannabliss Mode

Set `PROFILE=cannabliss` to build the Cannabliss 100-song public playlist from:

- `MASTER_PLAYLIST_ID` as the read-only Cannabliss Master source
- current default Cannabliss source: `47W5136lY5XazjWDHmfyxm` (`Cannabliss Master Clone`)
- `CANNABLISS_FEEDER_PLAYLIST_IDS` for discovery intake
- `CANNABLISS_HALL_OF_FAME_PLAYLIST_ID` for occasional legacy context
- current default public Cannabliss target: `3P9XkucRpg9Naz8cGyZOpW`

The Cannabliss builder:

- preserves a front-half structure (`1-10`, `11-25`, `26-40`, `41-50`)
- targets `100` total songs by default
- plans `25` new songs on major refreshes by default
- supports `major` and `micro` refresh modes
- records ordered run summaries to `CANNABLISS_STATE_PATH`
- writes only to `CANNABLISS_TARGET_PLAYLIST_ID`

Playlist read caching:

- source playlists are cached locally by playlist ID
- default TTL is `12` hours
- this reduces repeated large reads of the master clone and Hall of Fame
- use `FORCE_REFRESH=1` when you explicitly want fresh reads from Spotify
- scheduled Friday workflow runs use `FORCE_REFRESH=1` automatically

Optional personal-listening boosts:

- `CANNABLISS_USE_TOP_TRACKS=1` reads your Spotify top tracks
- `CANNABLISS_USE_RECENTLY_PLAYED=1` reads your recently played tracks
- these signals softly boost songs already in the Cannabliss pool
- if your token does not have the required scopes, the run warns and continues without those boosts

If you want to use those signals, regenerate your refresh token with:

- `user-top-read`
- `user-read-recently-played`

## Evolution Mode

Set `EVOLVE=1` to generate multiple playlist candidates (`CANDIDATES`) per run, score them, and choose the highest-scoring winner.
Scoring combines novelty, artist diversity, feature cohesion, and freshness using `SCORE_W_*` weights.
Each run appends a reproducible candidate/winner record to `EVOLVE_LOG_PATH` (JSONL, no secrets).
