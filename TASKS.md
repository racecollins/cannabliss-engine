# Tasks — Vertical Slices

## Slice 1: Config & Validation
**Files**: `src/config.py`, `requirements.txt`
**What**: Parse all env vars, validate required ones, provide defaults.
**Definition of Done**: `validate_config()` raises clear errors for missing vars; all defaults work.

## Slice 2: Spotify Client (Auth + API)
**Files**: `src/spotify_client.py`
**What**: Token refresh, paginated playlist read, playlist replace, description update, retry logic.
**Definition of Done**: Can obtain access token from refresh token; can read all tracks from a playlist; can replace playlist tracks.

## Slice 3: Selection Logic
**Files**: `src/selection.py`, `tests/test_selection.py`
**What**: Deduplication, filtering, recent mode, random mode, SEED support.
**Definition of Done**: Unit tests pass for both modes, dedup, filtering, edge cases.

## Slice 4: Main Entrypoint
**Files**: `src/main.py`
**What**: Wire config → client → selection → write. DRY_RUN support. Description update.
**Definition of Done**: Full end-to-end run in DRY_RUN mode works; live mode replaces playlist.

## Slice 5: Refresh Token Helper
**Files**: `src/refresh_token_helper.py`
**What**: Local one-time OAuth flow to obtain refresh token.
**Definition of Done**: Running script opens browser, completes auth, prints refresh token.

## Slice 6: CI/CD & Docs
**Files**: `.github/workflows/weekly.yml`, `README.md`
**What**: GitHub Actions weekly cron, secrets config, full README with setup instructions.
**Definition of Done**: Workflow file is valid YAML; README covers setup, auth, local run, CI, and smoke test.
