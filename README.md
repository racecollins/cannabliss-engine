# Cannabliss Engine

Cannabliss Engine automates the public Cannabliss Spotify playlist.

It builds a curated 100-song playlist from:
- a read-only Cannabliss Master source
- Hall of Fame context
- optional feeder playlists
- optional personal listening signals from Spotify top tracks and recently played tracks

The top ten blends listening strength, release freshness and bounded preferences learned from your reordering. Public additions become queued nominations for future editions; Master-only additions are discovery candidates.

## Project Docs

- [Cannabliss philosophy](./docs/cannabliss-philosophy.md)
- [Spotify project policy](./docs/spotify-project-policy.md)
- [New Spotify project starter](./docs/new-spotify-project-starter.md)
- [AI engineering guidelines](./AI_ENGINEERING_GUIDELINES.md)

## Setup

### 1. Spotify App

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Open your shared Spotify automation app
3. Ensure this redirect URI is configured:
   - `http://127.0.0.1:8888/callback`
4. Copy your:
   - `SPOTIFY_CLIENT_ID`
   - `SPOTIFY_CLIENT_SECRET`

### 2. Clone and Install

```bash
git clone https://github.com/racecollins/cannabliss-engine.git
cd cannabliss-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment

Create a `.env` file with your Cannabliss settings:

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
CANNABLISS_WEEKLY_INSERTIONS=20
CANNABLISS_UPDATE_MODE=major
CANNABLISS_MICRO_REFRESH_COUNT=5
CANNABLISS_PROTECTION_DAYS=14
CANNABLISS_DISCOVERY_PER_REFRESH=15
CANNABLISS_LEARN_TOP_TEN=1
CANNABLISS_QUEUE_CURATOR_ADDITIONS=1
CANNABLISS_CURATOR_QUEUE_PER_REFRESH=10
CANNABLISS_REMOVAL_COOLDOWN_DAYS=42
CANNABLISS_PREVIEW_PATH=data/preview/cannabliss.md
CANNABLISS_STATE_PATH=data/cannabliss_state.json
CANNABLISS_USE_TOP_TRACKS=1
CANNABLISS_USE_RECENTLY_PLAYED=1
CANNABLISS_TOP_TRACKS_TERM=short_term
CANNABLISS_TOP_TRACKS_LIMIT=50
CANNABLISS_RECENTLY_PLAYED_LIMIT=50
CANNABLISS_TOP_TRACKS_BOOST=0.35
CANNABLISS_RECENTLY_PLAYED_BOOST=0.25
MAX_TRACKS_PER_ARTIST=2
PLAYLIST_CACHE_DIR=data/cache/playlists
PLAYLIST_CACHE_TTL_HOURS=12
FORCE_REFRESH=0
DRY_RUN=1
```

### 4. Get Your Refresh Token

```bash
.venv/bin/python3 -m src.refresh_token_helper
```

If you want listening boosts, regenerate your token with scopes that include:
- `user-top-read`
- `user-read-recently-played`

## Usage

### Local Dry Runs

```bash
# Major refresh dry run
PROFILE=cannabliss CANNABLISS_UPDATE_MODE=major DRY_RUN=1 .venv/bin/python3 -m src.main

# Micro refresh dry run
PROFILE=cannabliss CANNABLISS_UPDATE_MODE=micro DRY_RUN=1 .venv/bin/python3 -m src.main

# Dry run with listening boosts
PROFILE=cannabliss CANNABLISS_USE_TOP_TRACKS=1 CANNABLISS_USE_RECENTLY_PLAYED=1 DRY_RUN=1 .venv/bin/python3 -m src.main

# Force-refresh playlist sources instead of using cache
FORCE_REFRESH=1 PROFILE=cannabliss DRY_RUN=1 .venv/bin/python3 -m src.main

# Live major refresh
PROFILE=cannabliss CANNABLISS_UPDATE_MODE=major DRY_RUN=0 .venv/bin/python3 -m src.main
```

### Run Tests

```bash
.venv/bin/python3 -m pytest tests/ -q
```

## GitHub Actions

**Activated September 30, 2026:** the approved 100-song edition is live and its
exact order was verified. A subsequent guarded live no-op passed. The weekly and
midweek workflows use durable public history on `cannabliss-state`, one shared
concurrency lock, tests before runs, and readback verification. Check the Actions
page for current run status. Manual dispatch defaults to preview-only.


### Required Secrets

In GitHub → Settings → Secrets and variables → Actions:

- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `SPOTIFY_REFRESH_TOKEN`

### Scheduled Workflows

This repo now has two scheduled Cannabliss workflows:

- `Cannabliss Weekly Update`
  - every Friday at `11:00 UTC`
  - `6:00 AM CDT` / `5:00 AM CST`
  - runs a `major` refresh

- `Cannabliss Midweek Micro Refresh`
  - every Monday and Wednesday at `15:00 UTC`
  - `10:00 AM CDT` / `9:00 AM CST`
  - runs a `micro` refresh

Scheduled runs force-refresh playlist sources so they use fresh Spotify data.
The live Cannabliss target playlist is always fetched fresh before planning an update so manual adds/removes made between runs are seen before the automation rewrites the playlist.

### Manual Trigger

From **Actions**, you can manually run either workflow and choose whether to do a dry run.

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
| `CANNABLISS_WEEKLY_INSERTIONS` |  | `20` | Shared weekly arrival ceiling |
| `CANNABLISS_UPDATE_MODE` |  | `major` | `major` or `micro` |
| `CANNABLISS_MICRO_REFRESH_COUNT` |  | `5` | Change budget for micro refresh |
| `CANNABLISS_PROTECTION_DAYS` | | `14` | Minimum stay for observed public-playlist picks |
| `CANNABLISS_DISCOVERY_PER_REFRESH` | | `15` | Maximum automatic admissions per weekly refresh |
| `CANNABLISS_PREVIEW_PATH` | | empty | Write full Markdown and JSON before/after reports |
| `CANNABLISS_STATE_PATH` |  | `data/cannabliss_state.json` | Cannabliss ordered-state log |
| `CANNABLISS_USE_TOP_TRACKS` |  | `1` | Enables ranked personal listening signals |
| `CANNABLISS_USE_RECENTLY_PLAYED` |  | `0` | `1` enables recently-played boosts |
| `CANNABLISS_TOP_TRACKS_TERM` |  | `short_term` | Spotify top-track window |
| `CANNABLISS_TOP_TRACKS_LIMIT` |  | `50` | Max top tracks to read |
| `CANNABLISS_RECENTLY_PLAYED_LIMIT` |  | `50` | Max recently played items to read |
| `CANNABLISS_TOP_TRACKS_BOOST` |  | `0.35` | Premium/current listening boost |
| `CANNABLISS_RECENTLY_PLAYED_BOOST` |  | `0.25` | Recent listening boost |
| `MAX_TRACKS_PER_ARTIST` |  | `2` | Artist cap used during Cannabliss build |
| `DRY_RUN` |  | `1` | `1` previews without Spotify writes |
| `PLAYLIST_CACHE_DIR` |  | `data/cache/playlists` | Local cache directory for playlist reads |
| `PLAYLIST_CACHE_TTL_HOURS` |  | `12` | Cache freshness window in hours |
| `FORCE_REFRESH` |  | `0` | `1` bypasses cache and refetches |

## Safety

- Cannabliss Master is read-only
- The public Cannabliss playlist is rewritten from the planned ordered result
- Playlist description is preserved during Cannabliss updates
- `DRY_RUN` mode prevents Spotify writes
- Secrets stay in env vars / GitHub secrets
- `.env` is gitignored

## Cannabliss Model

- **Master:** the read-only collection. Membership alone never protects or
  guarantees a place in public rotation.
- **Public additions:** saved as nominations at the next observation, eligible
  from the following Monday (UTC calendar week, based on Spotify addition time).
  Admit up to 10 per weekly major refresh, oldest eligible first, subject to the
  shared budget, protected capacity and artist limits. Same-week and midweek
  runs capture but do not promote them. Extra songs leave the public edition
  when the engine restores its 100-song size; full metadata stays in the queue,
  even when the song is absent from Master. Queue entries do not expire. Their
  14-day protection starts on admission, not while waiting. Songs added then
  removed before any engine observation cannot be captured. Previously live
  picks remain protected under their existing dates.
- **Top ten:** one lead artist per slot, ranked from the selected membership using
  recent Spotify affinity ranks, a bounded reorder preference and a small release
  freshness bonus. Two consecutive featured weeks trigger a week outside the top
  ten when the pool has sufficient artist diversity. No chart feed is wired in.
- **Learning:** compare live order against the last verified write. Pairwise
  reversals involving either top ten provide soft evidence; insertions, deletions
  and shifts they cause do not. This cannot identify the actor or the exact drag
  gesture, and edits undone before the next read cannot be observed. Pair evidence
  has a 42-day half-life, expires after 180 days and is capped at 500 entries.
  Preferences affect specific tracks, not inferred genres or permanent artist bans.
- **Weekly refresh:** normally up to 15 combined admissions within a shared
  20-song weekly allowance. With a backlog, up to 10 queued nominations leave
  room for five other candidates. Capturing nominations spends no allowance;
  admitting them does. Candidate shortages can mean fewer arrivals.
  Prefer tracks absent from recorded feature/listening signals, without claiming
  they have never been heard. An empty initial playlist can fill to 100.
- **Midweek/repeat runs:** preserve incumbent relative order, capture and park
  extra nominations, and fill permitted vacancies. Queue promotions wait for the
  next eligible weekly major refresh. Removing overflow nominations is intentional;
  it is not inferred as a dislike, retirement, or new listening preference.
- **Retirement:** oldest unprotected incumbents leave first; listening can delay
  retirement by at most three days. Automatic retirements rest for 42 days.
- **Manual removals:** stay excluded until explicitly re-added.
- **Size:** at most 100 unique tracks. If more than 100 picks are protected,
  stop and request an explicit choice instead of silently deleting your picks.
  Limited candidates/artist diversity/budget can leave the playlist below 100.
- **History:** rotation dates survive Spotify rewrites. Previews never advance
  history. Only a verified successful Spotify update does.

### First run of the repaired engine

The old committed history is stale and may include previews. It is retained as
an archive, but is not used to guess which songs you added recently. Establish a
new baseline from the live playlist, protecting its existing membership for 14
days. Initial ordering uses the Spotify addition dates available; earlier
rewrites may have reset those dates, so review the first preview carefully.
If the existing playlist exceeds 100 distinct protected songs, the engine stops
for a selection decision. It does not trim that baseline without your input.

```bash
DRY_RUN=1 FORCE_REFRESH=1 CANNABLISS_PREVIEW_PATH=data/preview/cannabliss.md .venv/bin/python -m src.main
```

This creates a readable complete before/after report and a JSON companion.
The reviewed edition was applied and verified on September 30, 2026. Scheduled state is restored to `data/runtime/cannabliss_state.json` from the public `cannabliss-state` branch. The committed legacy state file is not the live database.

### Discovery source access

Lorem, Anti-Pop and the account's Discover Weekly are intended inspiration
sources, not verified connected feeds. A September 30 read of Spotify's official
Lorem playlist returned 404; API search/account listing did not identify the
other two. Spotify development-mode access restricts playlist items to owned or
collaborative playlists:
https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide

An owned discovery inbox is a supported way to supply candidates from those
sources when direct access is unavailable. Existing feeder ingestion can read
that inbox using `CANNABLISS_FEEDER_PLAYLIST_IDS`. It has not been created or wired.
Membership in a feeder is inspiration, not verified musical-fit or trend evidence.
No system here claims complete lifetime listening history or trains an audio model.
