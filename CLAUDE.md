# CLAUDE.md — Cannabliss Engine

## What this is
Automation that keeps the **public Cannabliss Spotify playlist** (100 tracks) curated. Two parts in one repo:

1. **Python curation engine** (`src/`) — the product. Rebuilds the target playlist from a read-only Master + Hall of Fame + feeder playlists + your Spotify listening signals, using an evolutionary scoring/zone system. This is what runs on a schedule.
2. **Next.js "control center" dashboard** (`app/`, `components/`, `data/dashboard/`) — visualizes run history (`data/cannabliss_state.json`) plus live Spotify. **Secondary; deployment status unverified** — treat as not actively maintained until confirmed.

Status: **active**, runs live 3×/week. It lives under `projects/archive/` but is maintained, not retired. Handed off from Codex to Claude (June 2026).

## Architecture (engine)
- `src/main.py` — entrypoint (`python -m src.main`); wires config → client → curation → write.
- `src/cannabliss.py` — the curation brain: scoring, zones, selection, run-state I/O.
- `src/spotify_client.py` — thin Spotify Web API wrapper (auth, paginated reads, replace, retry/backoff).
- `src/config.py` — all config via env vars (validated; defaults live in the workflow YAMLs).
- `src/cache.py` — playlist read cache (`data/cache/playlists`, TTL hours).
- `src/refresh_token_helper.py` — one-time local OAuth (Authorization Code flow) to mint a refresh token.
- `data/cannabliss_state.json` — committed run history (the dashboard reads this).
- `.github/workflows/weekly.yml` — Fri **major** refresh. `cannabliss-micro.yml` — Mon/Wed **micro** refresh.

## Commands
```bash
.venv/bin/python -m pytest                 # run tests (local venv is py3.14; CI uses 3.12)
DRY_RUN=1 python -m src.main               # full run, no Spotify writes (always test this first)
python -m src.refresh_token_helper         # re-mint SPOTIFY_REFRESH_TOKEN (opens browser)
gh run list --limit 5                      # check live workflow health
```

## Spotify auth — READ THIS
- Flow: **Authorization Code** (user-authorized). One shared Spotify dev app; each repo gets its own `SPOTIFY_REFRESH_TOKEN`. See `docs/spotify-project-policy.md`.
- The token is wired into **4 places**: both workflow secrets + the dashboard's server fetch (`data/dashboard/liveSpotify.ts`).
- **Refresh tokens expire 6 months after the original sign-in** (Spotify change, enforced from **2026-07-20**). Refreshing does **not** extend the lifetime — it's anchored to original auth, so running more often does not help.
- On expiry → token endpoint returns `invalid_grant` (400):
  - **Engine** → all 3 workflows fail hard; playlist stops updating; GitHub emails you.
  - **Dashboard** → silently falls back to local/mock data (no crash).
- **Fix (recurring, ~2 min):** run `python -m src.refresh_token_helper` → copy token → update the `SPOTIFY_REFRESH_TOKEN` GitHub Actions secret → update `.env`. Repeat every ~5–6 months.
- `SpotifyAuthError` (`src/spotify_client.py`) detects this case and prints the exact recovery steps. Apple Reminders nudge set for 2026-07-15. Do **not** build token-rotation/persistence to dodge re-auth — it can't extend a lifetime anchored to original sign-in.

## Conventions & gotchas
- **Master playlist is read-only.** Never modify it. The engine only replaces the target playlist.
- Reads/writes use the `/playlists/{id}/items` endpoint (not `/tracks`) — more reliable for some playlists.
- Minimal deps on purpose: `requests` only, no `spotipy`.
- **`SPEC.md` and `TASKS.md` are STALE** — they describe the removed legacy "Fresh 100" random/recent picker, not the current engine. Don't trust them; rewrite or delete when convenient.
- Secrets: never open `.env` or token files with Read (global policy) — manipulate in place.

## Working agreements
- TDD for engine changes (tests in `tests/`, `monkeypatch` the `requests` layer — no live API in tests).
- `DRY_RUN=1` before any live write. Stagger any new Spotify automations' schedules (shared app rate limits).
