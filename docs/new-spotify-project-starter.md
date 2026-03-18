# New Spotify Project Starter

Use this as the opening prompt for a new Codex thread when starting a separate Spotify automation repo.

```text
This is a new Spotify automation project separate from Cannabliss.

Use the same Spotify Developer app pattern as my Cannabliss setup:
- reuse SPOTIFY_CLIENT_ID
- reuse SPOTIFY_CLIENT_SECRET
- use a separate SPOTIFY_REFRESH_TOKEN for this repo
- keep scopes as narrow as practical for this project
- keep playlist IDs, .env, GitHub secrets, and workflow config isolated to this repo
- assume this project should not affect Cannabliss or other Spotify repos

Please help me design and implement this as a separate Spotify project.

When making recommendations, prefer:
- one repo per distinct Spotify automation
- DRY_RUN support before live writes
- explicit source and target playlist boundaries
- a simple GitHub Actions workflow only if the project is stable enough for automation
```

## Quick Checklist

Before starting the new repo, decide:

1. Project goal
2. Source playlists or Spotify inputs
3. Target playlists or outputs
4. Required scopes
5. Whether this should stay manual first or be scheduled

## When To Use A New Repo

Create a new repo when the new Spotify tool is meaningfully separate from Cannabliss.

Stay in the current repo only when the work is still part of the same playlist automation system.
