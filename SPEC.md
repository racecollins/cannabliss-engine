# Fresh 100 — Specification

## Overview
Automated Spotify playlist curator that maintains a "Fresh 100" playlist derived from a large "Master" playlist. Runs locally or via GitHub Actions on a weekly schedule.

## Requirements

### Functional
1. **Read** all tracks from the Master playlist (paginated, handles 3000+ tracks).
2. **Select** 100 tracks using one of two modes:
   - `random` (default for weekly cron): uniformly sample 100 distinct tracks.
   - `recent`: pick the 100 most recently added tracks by `added_at`.
3. **Deduplicate**: If the same track URI appears multiple times in Master, treat it as one track. For `recent` mode, keep the most recent `added_at` instance.
4. **Filter**: Skip non-track items (podcasts/episodes) and unavailable/null tracks.
5. **Replace** the entire Fresh 100 playlist contents with the selected tracks.
6. **Update playlist description** with run metadata (date, mode, count).
7. **DRY_RUN mode**: Print selected tracks without writing to Spotify.
8. **Deterministic random**: When `SEED` env var is set, random selection is reproducible.

### Non-Functional
1. Minimal dependencies: `requests` only (no spotipy or similar).
2. Simple retry with exponential backoff for HTTP 429 (rate limit).
3. Clear, concise logging to stdout.
4. All configuration via environment variables.
5. Runnable on Python 3.11+.

## Non-Goals
- We do NOT modify the Master playlist in any way.
- We do NOT manage playlist followers.
- We do NOT handle initial Spotify app creation (README guides user).
- We do NOT support interactive OAuth during CI — refresh token is pre-obtained.
- We do NOT build a web UI.

## Edge Cases
| Case | Behavior |
|------|----------|
| Master has < COUNT usable tracks | Use all available, log warning |
| Master is empty | Exit with warning, no changes to Fresh 100 |
| Track appears multiple times in Master | Deduplicate by track URI |
| Podcast/episode in Master | Filter out silently |
| Track is `null` or has no URI | Skip |
| Spotify returns 429 | Retry up to 3 times with exponential backoff |
| Refresh token expired/invalid | Exit with clear error message |
| Fresh 100 playlist doesn't exist | Exit with error (user must pre-create it) |
| SEED provided in random mode | Use as random seed for reproducibility |
| SEED provided in recent mode | Ignored |

## API Approach
- **Auth**: OAuth 2.0 Authorization Code flow. One-time local helper obtains refresh token. Main script uses refresh token → access token exchange.
- **Read Master**: `GET /v1/playlists/{id}/tracks` with pagination (limit=100, offset+=100).
- **Write Fresh 100**: `PUT /v1/playlists/{id}/tracks` to replace all tracks (max 100 URIs per call; one call suffices for COUNT=100).
- **Update Description**: `PUT /v1/playlists/{id}` with new description string.

## Repo Structure
```
spotify-fresh-100/
├── SPEC.md
├── TASKS.md
├── README.md
├── requirements.txt
├── src/
│   ├── main.py
│   ├── spotify_client.py
│   ├── selection.py
│   ├── config.py
│   └── refresh_token_helper.py
├── tests/
│   └── test_selection.py
└── .github/
    └── workflows/
        └── weekly.yml
```

## Acceptance Criteria
- [ ] `python src/main.py` with DRY_RUN=1 prints 100 track names without Spotify writes.
- [ ] `python src/main.py` with DRY_RUN=0 replaces Fresh 100 playlist contents.
- [ ] `python -m pytest tests/` passes all tests.
- [ ] GitHub Actions workflow runs weekly with secrets.
- [ ] Master playlist is never modified.
- [ ] Duplicate tracks in Master produce unique selections.
- [ ] SEED produces identical random selections across runs.
