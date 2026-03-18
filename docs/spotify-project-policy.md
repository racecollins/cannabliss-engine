# Spotify Project Policy

## Summary

This repo uses a single Spotify Developer app as a shared auth container for personal Spotify automations. Because Spotify currently limits this account to one Development Mode app, project isolation happens at the repo and token level rather than at the app level.

Use this document as the default policy when creating future Spotify automation repos.

## Final Policy

- Use one Spotify Developer app as the personal automation app.
- Reuse the same:
  - `SPOTIFY_CLIENT_ID`
  - `SPOTIFY_CLIENT_SECRET`
- Give each repo or project its own:
  - `SPOTIFY_REFRESH_TOKEN`
  - playlist IDs
  - `.env`
  - GitHub Actions secrets
  - workflow defaults
  - scope documentation

## Scope Rules

- Keep scopes as narrow as practical per repo.
- When a repo needs new scopes, generate a new refresh token for that repo.
- Do not assume one refresh token should be reused across all Spotify projects.
- Add new redirect URIs to the Spotify app settings without removing old working URIs.

## Operational Rules

- Treat each repo as an isolated automation even though it shares the same Spotify app.
- Keep a short repo note that records:
  - purpose of the project
  - required scopes
  - source playlists
  - target playlists
  - workflow schedule
- Stagger workflow schedules across repos to reduce shared app-level rate-limit collisions.
- Test new repos with `DRY_RUN=1` before any live Spotify writes.

## Repo Boundary Rule

Use a new repo when the Spotify automation is a different product or workflow, for example:

- a playlist curation system
- a Shazam-to-Spotify sync tool
- a discovery intake tool
- an analytics or reporting workflow

Use a new thread without a new repo only when the work is still part of the same codebase.

## Cannabliss-Specific Note

Cannabliss remains part of this repo for now. Future unrelated Spotify automations should usually go in their own repo and follow this policy.
