# Cannabliss Fresh Front — Design

**Date:** 2026-06-19
**Status:** Draft for review
**Branch:** `feature/fresh-front-top15`

## Goal

Make the **front of the public Cannabliss playlist a mirror of the songs Race hand-adds**, freshest first. The top of the playlist should feel like "what I'm vibing with right now," refreshed every Friday and nudged toward the top throughout the week.

Concretely:

1. The **top 15** of the public playlist are the freshest songs Race added to it, newest on top.
2. Songs added **during the week** (Fri → Thu) are pulled toward the top by the Mon/Wed refreshes, not just on Friday.
3. A song that is **both** in the playlist **and** in Race's heavy listening rotation lands in the **top 5**.
4. At most **2 songs per artist** in the top 15, so a 5–7 song artist binge can't swallow the front.
5. A song that was **removed** (retired by the engine, or deleted by Race) is **not re-added the following week**.

## Why this is (mostly) a simplification

The engine already ranks freshness off a song's *add date* and already loads listening signals. But today's front-building logic is an indirect tangle: `MAJOR_TOP_10_FRESH_TARGET = 8` + `MAJOR_TOP_10_CARRYOVER_LIMIT = 2`, a 21-day `front_queue` window keyed off the **Master/feeder** add-date, and a "signaled tracks" pool — all aimed at *inferring* what should be up top.

This design replaces that inference with the **direct signal Race already gives**: the songs he puts into the public playlist. The front becomes one clear rule instead of four interacting ones.

## Key insight: the write mechanism makes "Race's adds" trivially detectable

`SpotifyClient.replace_playlist_tracks` writes the playlist with a single `PUT .../items` that **replaces all tracks at once**. Spotify stamps every engine-written track with the *same* `added_at` (the run time). Therefore:

- Any song **Race** adds during the week has an `added_at` strictly newer than that uniform block.
- It is also **absent from the previous run's recorded `track_ids`** in `data/cannabliss_state.json`.

Either signal identifies Race's weekly adds. We use the **state comparison** as the primary, authoritative signal (it does not depend on timestamp quirks), and `added_at` for ordering within the fresh set.

## Definitions

Let the run being computed be run *N*, with injected `now`.

- **prev_run_uris** — the `track_ids` of the most recent prior run in state, reconstructed to URIs (`spotify:track:<id>`). Empty on the first run.
- **current_uris** — URIs currently in the public playlist (read live each run; the playlist has grown to ~110–125 by Friday).
- **weekly_adds** — `current_uris − prev_run_uris`. These are the songs Race added since the last run. They are *protected* (see below) and *honored over cooldown*.
- **incumbents** — `current_uris ∩ prev_run_uris`. Songs the engine placed last run and Race kept.
- **top_played** — `listening_signals.top_track_ids` (Spotify `short_term` top tracks, ~last 4 weeks — the closest the API offers to "past week").
- **recently_played** — `listening_signals.recently_played_ids` (last ~50 plays; skews to the last few days).
- **hot_pick** — a song that is **in the playlist** (a `weekly_add` or `incumbent`) **and** in `top_played`. These are the top-5 candidates.
- **cooldown set** — URIs removed in the cooldown window (default 7 days); see Removal Cooldown.

> **Listening window caveat (accepted):** Spotify's smallest top-tracks window is `short_term` (~4 weeks), not literally 7 days. `recently_played` is the more recent-skewing signal. We combine the two as the "listening a lot lately" signal and accept this is a proxy for "past week."

## Front ordering (the heart of the change)

The front tier size is configurable: **`CANNABLISS_FRESH_FRONT_SIZE`, default 15.** Call it `F`.

Build the front candidate pool, in priority order:

1. `weekly_adds` (Race's picks this cycle)
2. **in-playlist hot picks** — any song already in the playlist that is in `top_played`. Included *unconditionally* (even in a heavy-add week) so a heavily-played song is always eligible for the top 5, per the rule above.
3. **rolling fill** when the pool is still under `F` — the next-freshest songs:
   - incumbents that were recent adds in prior cycles (still high freshness),
   - recent Master/feeder re-adds (the "pull off Master and re-add to refresh" trick),
   - listening favorites already in the playlist.

Exclude any URI in the **cooldown set** from the in-playlist-hot-pick and rolling-fill pools. `weekly_adds` are **never** excluded by cooldown (a manual re-add is an explicit override).

> **Note on incumbent freshness:** the full-replace write resets `added_at` on all engine-placed tracks to the last run time, so incumbents share one freshness value and can't be ordered by recency *among themselves*. That's fine — `weekly_adds` (distinct, newer timestamps) order correctly, and within the incumbent band the `is_hot_pick`-first key and the listening boost do the ordering.

**Sort the pool** by this key, descending:

1. **`is_hot_pick`** (boolean) — hot picks sort first. With ≤5 hot picks they occupy the top 5; this is how "added + heavily played → top 5" is delivered.
2. **freshness + listening score** — primarily add-recency (newest first), plus a listening boost (`top_played` > `recently_played`) that lifts a song a few spots within its freshness band.
3. Stable tie-breakers (added_at, name, uri) — as today.

**Apply the artist cap while taking the top `F`:** at most **2 songs per primary artist** in the top 15 (`MAJOR_FRESH_FRONT_MAX_PER_ARTIST = 2`). When Race adds 5–7 songs of one artist, only the best 2 enter the top 15; the remainder are **not discarded** — they flow into the lower zones (still protected this cycle).

## Protection and trimming (Friday / major)

- **Protected set** = `weekly_adds`. The Friday rebuild may reorder them but must **not drop** them, even the artist-binge overflow that didn't make the top 15.
- The playlist grew to ~110–125; the rebuild trims back to `CANNABLISS_TARGET_SIZE` (100). **Trimming comes off the bottom** — oldest/weakest incumbents retire first. Protected songs are exempt from trimming.
- Net effect: ~10–20 of the oldest songs retire each Friday (the accepted cost of a fast-moving front).

## Mid-week behavior (Mon/Wed / micro)

Micro runs **promote and preserve**:

- Detect `weekly_adds` since the previous run and **lift them to the top** (same front ordering, same hot-pick/top-5 and 2-per-artist rules).
- **Preserve everything else** — micro does not retire songs (keeps today's "grow, don't trim" behavior). A song added Monday rides near the top by Tuesday.

Because every run promotes-and-preserves, comparing each run to the *immediately previous* run is sufficient: by Friday the front reflects the whole week's adds without needing a separate week-long baseline.

## Removal Cooldown

Goal: a removed song is not re-added the following week. Override: a manual re-add by Race wins.

**State:** add a top-level `cooldown` list to `data/cannabliss_state.json`:

```json
"cooldown": [ { "uri": "spotify:track:...", "removed_at": "2026-06-19T11:00:00+00:00" } ]
```

**On each run:**

1. **Load & prune** — drop entries older than `CANNABLISS_REMOVAL_COOLDOWN_DAYS` (default **7**), measured against injected `now`. The survivors form the active cooldown set.
2. **Exclude** cooldown URIs from automatic candidate pools (rolling fill, discovery, stabilizers, library). Do **not** exclude `weekly_adds` (manual re-add override).
3. **After building** the new order, record newly-removed URIs with `removed_at = now`:
   - `user_removed = prev_run_uris − current_uris` (Race deleted it during the week), and
   - `engine_removed = (current_uris ∪ prev_run_uris) − new_output_uris` (retired by the trim),
   - minus anything present in the new output. Append the union to `cooldown`.

A song stays benched for `COOLDOWN_DAYS` and then becomes eligible again — matching "for the following week," not a permanent ban.

## Configuration (new env vars)

| Var | Default | Meaning |
|-----|---------|---------|
| `CANNABLISS_FRESH_FRONT_SIZE` | `15` | Size of the fresh front tier |
| `CANNABLISS_FRESH_FRONT_MAX_PER_ARTIST` | `2` | Max songs per artist within the front tier |
| `CANNABLISS_REMOVAL_COOLDOWN_DAYS` | `7` | How long a removed song is benched |

Listening boosts reuse the existing `CANNABLISS_TOP_TRACKS_BOOST` / `CANNABLISS_RECENTLY_PLAYED_BOOST`. The `is_hot_pick`-first sort makes "added + top-played → top 5" robust regardless of exact boost magnitudes. Both workflow YAMLs (`weekly.yml`, `cannabliss-micro.yml`) get the new vars; existing defaults preserved.

## Components touched

- `src/cannabliss.py` — replace the major/micro front-building blocks in `build_cannabliss_playlist` with: weekly-adds detection, front ordering (hot-pick-first + freshness/listening + 2-per-artist cap), protection-from-trim, and cooldown filtering/recording. Add small helpers (`_weekly_adds`, `_is_hot_pick`, `_build_fresh_front`, cooldown load/prune/record). Remove now-dead front constants/logic (`MAJOR_TOP_10_FRESH_TARGET`, `MAJOR_TOP_10_CARRYOVER_LIMIT`, the `front_queue` machinery) where superseded.
- `src/config.py` — three new validated env vars.
- `.github/workflows/weekly.yml`, `.github/workflows/cannabliss-micro.yml` — pass the new vars.
- `data/cannabliss_state.json` — gains a `cooldown` key (backward-compatible: absent → empty).
- `docs/cannabliss-philosophy.md` — update the "1-10 Premium Current Tier" section, which currently says the opposite ("the top 10 should not simply be the 10 newest songs").

## Edge cases

- **First run / no prior runs** — no `prev_run_uris`; treat all current as incumbents and build the front from the freshest available (existing `is_initial_build` path), no cooldown.
- **Fewer than `F` weekly adds** (e.g. 2, 8, 14) — rolling fill tops up to `F` from next-freshest; never errors, never pads with stale junk.
- **More than `F` weekly adds** — top `F` taken (artist-capped); overflow placed below, still protected.
- **Artist binge (5–7 of one artist)** — max 2 in top 15; the rest kept lower in the playlist (not discarded).
- **Race re-adds a benched song** — appears as a weekly add → honored, removed from cooldown.
- **Song both retired and re-added same week** — presence in new output wins; not added to cooldown.
- **`track_id` → URI reconstruction** — state stores bare ids; rebuild as `spotify:track:<id>`. Local tracks are already filtered upstream.

## Testing (TDD; monkeypatch the `requests` layer — no live API)

New `tests/test_cannabliss.py` cases:

1. Weekly adds detected as `current − prev_run` and placed at the front, newest first.
2. Rolling fill when weekly adds < `F` (e.g. 8 adds → 15-song front, 7 from fill).
3. Hot pick (in playlist + `top_played`) lands in the top 5, ahead of fresher non-hot adds.
4. 2-per-artist cap on a 6-song artist binge: 2 in top 15, other 4 retained lower, none dropped.
5. Protection: weekly adds survive the trim to 100; trimming removes oldest incumbents.
6. Cooldown: an engine-retired song is excluded next run; a Race-deleted song is excluded next run.
7. Cooldown override: a benched song Race re-adds is honored and cleared from cooldown.
8. Cooldown expiry: an entry older than `COOLDOWN_DAYS` no longer excludes (uses injected `now`).
9. Micro run promotes weekly adds to the top and preserves the rest (no retirement).
10. First-run path unaffected.

Plus `tests/test_config.py`-style validation for the three new env vars.

## Out of scope

- No token-rotation / persistence changes (per project policy).
- No dashboard changes.
- No new listening-data source beyond the existing top-tracks / recently-played APIs.
- Cooldown is time-boxed (default 7 days), not a permanent block-list.
