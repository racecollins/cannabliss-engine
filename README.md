# 🎵 Spotify Fresh 100

Automated playlist curator that maintains a **Fresh 100** playlist from your large **Master** playlist. Picks 100 random (or most recent) tracks weekly and replaces the Fresh 100 playlist contents.

## How It Works

1. Reads all tracks from your Master playlist (~3000 songs)
2. Filters out podcasts, episodes, local files, and duplicates
3. Selects 100 tracks (random or most recent)
4. Replaces your Fresh 100 playlist with the selection
5. Updates the playlist description with run metadata

Runs locally or automatically via GitHub Actions every Monday.

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
git clone <your-repo-url> && cd spotify-fresh-100
pip install -r requirements.txt
```

### 3. Configure Environment

Create a `.env` file:

```env
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
MASTER_PLAYLIST_ID=3P9XkucRpg9Naz8cGyZOpW
FRESH_PLAYLIST_ID=1h9wSgaNgFMTvt73qrgccn
MODE=random
COUNT=100
DRY_RUN=0
HISTORY_WEEKS=6
MAX_TRACKS_PER_ARTIST=2
FRESH_DAYS_1=30
FRESH_DAYS_2=180
ARCHIVE=0
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

The workflow runs **every Monday at 9:00 AM UTC** automatically. You can also trigger it manually from the **Actions** tab with options for mode, seed, dry run, history window, artist cap, freshness tiers, and archive mode.

### Manual Trigger

Go to **Actions → Fresh 100 Weekly Update → Run workflow** and choose your options.

---

## Environment Variables

| Variable                 | Required | Default    | Description                              |
|--------------------------|----------|------------|------------------------------------------|
| `SPOTIFY_CLIENT_ID`      | ✅       |            | Spotify app client ID                    |
| `SPOTIFY_CLIENT_SECRET`  | ✅       |            | Spotify app client secret                |
| `SPOTIFY_REFRESH_TOKEN`  | ✅       |            | OAuth refresh token                      |
| `MASTER_PLAYLIST_ID`     | ✅       |            | Source playlist ID                       |
| `FRESH_PLAYLIST_ID`      | ✅       |            | Destination playlist ID                  |
| `MODE`                   |          | `random`   | `random` or `recent`                     |
| `COUNT`                  |          | `100`      | Number of tracks to select               |
| `DRY_RUN`                |          | `0`        | `1` to preview without Spotify writes    |
| `SEED`                   |          |            | Random seed for reproducible selection   |
| `HISTORY_WEEKS`          |          | `6`        | Exclude tracks from last N runs          |
| `MAX_TRACKS_PER_ARTIST`  |          | `2`        | Artist cap per selection                 |
| `FRESH_DAYS_1`           |          | `30`       | Recent-tier days (weight 3 in random)    |
| `FRESH_DAYS_2`           |          | `180`      | Mid-tier days (weight 2 in random)       |
| `ARCHIVE`                |          | `0`        | `1` to create dated archive playlist     |

---

## Safety

- ✅ Master playlist is **never modified** — only read
- ✅ Fresh 100 is **replaced entirely** each run — no bloat
- ✅ No secrets in code — all via env vars / GitHub Secrets
- ✅ DRY_RUN mode for safe previews
- ✅ `.env` is gitignored
