# Cannabliss Fresh Front Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the front of the public Cannabliss playlist a mirror of the songs Race hand-adds (freshest first, top-played → top 5, 2-per-artist cap), protect those adds, bench removed songs for a week, and collapse the back-half scoring into one honest body score.

**Architecture:** `build_cannabliss_playlist` is rewritten from "infer a fresh front from Master/feeder freshness" to "the front *is* the songs in the live playlist that weren't there last run" (detected by diffing the live playlist against the previous run's recorded `track_ids`). New pure helpers carry the logic; the build function becomes a thin orchestrator. Below the front, one `_body_score` replaces the five `score_kind` branches and the tail/zone machinery. A removal cooldown (stored in `data/cannabliss_state.json`) prevents re-adds.

**Tech Stack:** Python 3.12 (CI) / 3.14 (local venv), `requests` only, `pytest`, `monkeypatch`. Next.js/TS dashboard (secondary). GitHub Actions workflows.

## Global Constraints

- **TDD always.** Every behavior change starts with a failing test. Monkeypatch the `requests` layer — no live Spotify API in tests.
- **`DRY_RUN=1` before any live write** (manual verification only; not part of automated tests).
- **Minimal deps:** `requests` only. No new Python dependencies.
- **Master playlist is read-only.** The engine only rebuilds the target playlist.
- **Secrets:** never open `.env`/token files with Read; manipulate in place.
- **Spec:** `docs/superpowers/specs/2026-06-19-cannabliss-fresh-front-design.md` is the source of truth.
- **Local test command:** `.venv/bin/python -m pytest` (venv is 3.14).
- **New config defaults (copy verbatim):** `CANNABLISS_FRESH_FRONT_SIZE=15`, `CANNABLISS_FRESH_FRONT_MAX_PER_ARTIST=2`, `CANNABLISS_REMOVAL_COOLDOWN_DAYS=7`.
- **Two real tiers only:** `zones` becomes `{"fresh_front": [...], "body": [...]}`.

---

### Task 1: Config — three new env vars

**Files:**
- Modify: `src/config.py` (dataclass `Config`, `load_config`, `validate_config`)
- Test: `tests/test_config.py` (create)

**Interfaces:**
- Produces: `Config.cannabliss_fresh_front_size: int`, `Config.cannabliss_fresh_front_max_per_artist: int`, `Config.cannabliss_removal_cooldown_days: int` (loaded from `CANNABLISS_FRESH_FRONT_SIZE` default `15`, `CANNABLISS_FRESH_FRONT_MAX_PER_ARTIST` default `2`, `CANNABLISS_REMOVAL_COOLDOWN_DAYS` default `7`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
"""Tests for config parsing/validation of the fresh-front settings."""

import pytest

from src.config import load_config, validate_config


REQUIRED_ENV = {
    "SPOTIFY_CLIENT_ID": "id",
    "SPOTIFY_CLIENT_SECRET": "secret",
    "SPOTIFY_REFRESH_TOKEN": "token",
    "MASTER_PLAYLIST_ID": "master123",
    "CANNABLISS_TARGET_PLAYLIST_ID": "target123",
}


def _set_env(monkeypatch, **overrides):
    for key in list(REQUIRED_ENV) + [
        "CANNABLISS_FRESH_FRONT_SIZE",
        "CANNABLISS_FRESH_FRONT_MAX_PER_ARTIST",
        "CANNABLISS_REMOVAL_COOLDOWN_DAYS",
    ]:
        monkeypatch.delenv(key, raising=False)
    for key, value in {**REQUIRED_ENV, **overrides}.items():
        monkeypatch.setenv(key, value)


def test_fresh_front_defaults(monkeypatch):
    _set_env(monkeypatch)
    cfg = load_config()
    assert cfg.cannabliss_fresh_front_size == 15
    assert cfg.cannabliss_fresh_front_max_per_artist == 2
    assert cfg.cannabliss_removal_cooldown_days == 7


def test_fresh_front_overrides(monkeypatch):
    _set_env(
        monkeypatch,
        CANNABLISS_FRESH_FRONT_SIZE="20",
        CANNABLISS_FRESH_FRONT_MAX_PER_ARTIST="1",
        CANNABLISS_REMOVAL_COOLDOWN_DAYS="14",
    )
    cfg = load_config()
    assert cfg.cannabliss_fresh_front_size == 20
    assert cfg.cannabliss_fresh_front_max_per_artist == 1
    assert cfg.cannabliss_removal_cooldown_days == 14


def test_invalid_fresh_front_size_exits(monkeypatch):
    _set_env(monkeypatch, CANNABLISS_FRESH_FRONT_SIZE="0")
    with pytest.raises(SystemExit):
        validate_config(load_config())


def test_invalid_cooldown_days_exits(monkeypatch):
    _set_env(monkeypatch, CANNABLISS_REMOVAL_COOLDOWN_DAYS="-1")
    with pytest.raises(SystemExit):
        validate_config(load_config())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL — `AttributeError: 'Config' object has no attribute 'cannabliss_fresh_front_size'`.

- [ ] **Step 3: Add the fields to the `Config` dataclass**

In `src/config.py`, add to the `@dataclass(frozen=True) class Config` body (after `cannabliss_micro_refresh_count: int`):

```python
    cannabliss_fresh_front_size: int
    cannabliss_fresh_front_max_per_artist: int
    cannabliss_removal_cooldown_days: int
```

- [ ] **Step 4: Load the new vars in `load_config`**

In `load_config`'s `Config(...)` call, add (after `cannabliss_micro_refresh_count=...`):

```python
        cannabliss_fresh_front_size=int(_env("CANNABLISS_FRESH_FRONT_SIZE", "15")),
        cannabliss_fresh_front_max_per_artist=int(_env("CANNABLISS_FRESH_FRONT_MAX_PER_ARTIST", "2")),
        cannabliss_removal_cooldown_days=int(_env("CANNABLISS_REMOVAL_COOLDOWN_DAYS", "7")),
```

- [ ] **Step 5: Validate the new vars in `validate_config`**

In `src/config.py`, add to `validate_config` (before the `if errors:` block):

```python
    if cfg.cannabliss_fresh_front_size < 1:
        errors.append(
            f"CANNABLISS_FRESH_FRONT_SIZE must be >= 1, got {cfg.cannabliss_fresh_front_size}"
        )
    if cfg.cannabliss_fresh_front_max_per_artist < 1:
        errors.append(
            "CANNABLISS_FRESH_FRONT_MAX_PER_ARTIST must be >= 1, "
            f"got {cfg.cannabliss_fresh_front_max_per_artist}"
        )
    if cfg.cannabliss_removal_cooldown_days < 0:
        errors.append(
            "CANNABLISS_REMOVAL_COOLDOWN_DAYS must be >= 0, "
            f"got {cfg.cannabliss_removal_cooldown_days}"
        )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: PASS (4 passed).

- [ ] **Step 7: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat(config): add fresh-front size, artist cap, and cooldown env vars"
```

---

### Task 2: Cooldown pure helpers

**Files:**
- Modify: `src/cannabliss.py` (add `timedelta` import; add `active_cooldown_uris`, `merge_cooldown`)
- Test: `tests/test_cooldown.py` (create)

**Interfaces:**
- Produces:
  - `active_cooldown_uris(cooldown_entries: list[dict], now: datetime, *, days: int) -> set[str]` — URIs whose `removed_at` is within `days` of `now`.
  - `merge_cooldown(cooldown_entries: list[dict], removed_uris: list[str], now: datetime, *, days: int) -> list[dict]` — prunes expired entries, appends newly-removed URIs stamped `now`, dedupes by URI.
  - Each entry is `{"uri": str, "removed_at": ISO-8601 str}`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cooldown.py`:

```python
"""Tests for the removal-cooldown helpers."""

from datetime import datetime, timezone

from src.cannabliss import active_cooldown_uris, merge_cooldown


NOW = datetime(2026, 6, 19, tzinfo=timezone.utc)


def _entry(uri, days_ago):
    removed = datetime(2026, 6, 19 - days_ago, tzinfo=timezone.utc)
    return {"uri": uri, "removed_at": removed.isoformat()}


def test_active_cooldown_includes_recent_excludes_expired():
    entries = [_entry("spotify:track:a", 2), _entry("spotify:track:b", 10)]
    active = active_cooldown_uris(entries, NOW, days=7)
    assert active == {"spotify:track:a"}


def test_active_cooldown_handles_missing_or_bad_timestamps():
    entries = [{"uri": "spotify:track:x"}, {"uri": "spotify:track:y", "removed_at": "nonsense"}]
    assert active_cooldown_uris(entries, NOW, days=7) == set()


def test_merge_cooldown_appends_new_and_prunes_expired():
    entries = [_entry("spotify:track:old", 10), _entry("spotify:track:keep", 1)]
    merged = merge_cooldown(entries, ["spotify:track:new"], NOW, days=7)
    uris = {e["uri"] for e in merged}
    assert uris == {"spotify:track:keep", "spotify:track:new"}
    new_entry = next(e for e in merged if e["uri"] == "spotify:track:new")
    assert new_entry["removed_at"] == NOW.isoformat()


def test_merge_cooldown_does_not_duplicate_existing_uri():
    entries = [_entry("spotify:track:keep", 1)]
    merged = merge_cooldown(entries, ["spotify:track:keep"], NOW, days=7)
    assert [e["uri"] for e in merged] == ["spotify:track:keep"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_cooldown.py -v`
Expected: FAIL — `ImportError: cannot import name 'active_cooldown_uris'`.

- [ ] **Step 3: Add the import**

In `src/cannabliss.py`, change the datetime import line:

```python
from datetime import date, datetime, timedelta, timezone
```

- [ ] **Step 4: Implement the helpers**

Add to `src/cannabliss.py` (near the other module-level helpers, e.g. above `track_id`):

```python
def active_cooldown_uris(
    cooldown_entries: list[dict], now: datetime, *, days: int
) -> set[str]:
    """URIs removed within the cooldown window (`days`) — excluded from re-add."""
    cutoff = now - timedelta(days=days)
    active: set[str] = set()
    for entry in cooldown_entries:
        removed_at = _parse_datetime(entry.get("removed_at", ""))
        uri = entry.get("uri")
        if removed_at is None or not uri:
            continue
        if removed_at >= cutoff:
            active.add(uri)
    return active


def merge_cooldown(
    cooldown_entries: list[dict],
    removed_uris: list[str],
    now: datetime,
    *,
    days: int,
) -> list[dict]:
    """Prune expired entries, then append newly-removed URIs stamped `now`."""
    cutoff = now - timedelta(days=days)
    kept: list[dict] = []
    seen: set[str] = set()
    for entry in cooldown_entries:
        removed_at = _parse_datetime(entry.get("removed_at", ""))
        uri = entry.get("uri")
        if removed_at is None or not uri or removed_at < cutoff:
            continue
        if uri in seen:
            continue
        seen.add(uri)
        kept.append({"uri": uri, "removed_at": entry["removed_at"]})
    stamp = now.isoformat()
    for uri in removed_uris:
        if uri and uri not in seen:
            seen.add(uri)
            kept.append({"uri": uri, "removed_at": stamp})
    return kept
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_cooldown.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add src/cannabliss.py tests/test_cooldown.py
git commit -m "feat(cannabliss): add removal-cooldown helpers"
```

---

### Task 3: Detection + scoring helpers

**Files:**
- Modify: `src/cannabliss.py` (add constants; add `_is_hot_pick`, `_front_score`, `_body_score`, `_front_sort_key`, `_body_sort_key`)
- Test: `tests/test_scoring_helpers.py` (create)

**Interfaces:**
- Produces:
  - `_is_hot_pick(track: CannablissTrack, signals: ListeningSignals) -> bool` — true when the track's id is in `signals.top_track_ids`.
  - `_front_score(track, signals, now) -> float` — `_recency_score` + full top/recent listening boosts.
  - `_body_score(track, signals, now) -> float` — `_recency_score` + half listening boosts + weak popularity + Hall penalty.
  - `_front_sort_key(track, signals, now, weekly_add_ids: set[str]) -> tuple` — used with `reverse=True`.
  - `_body_sort_key(track, signals, now) -> tuple` — used with `reverse=True`.
- Module constants: `DEFAULT_FRESH_FRONT_SIZE = 15`, `DEFAULT_FRESH_FRONT_MAX_PER_ARTIST = 2`, `DEFAULT_REMOVAL_COOLDOWN_DAYS = 7`, `HALL_BODY_PENALTY = 0.05`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_scoring_helpers.py`:

```python
"""Tests for fresh-front / body scoring helpers."""

from datetime import datetime, timezone

from src.cannabliss import (
    CannablissTrack,
    ListeningSignals,
    _body_score,
    _body_sort_key,
    _front_score,
    _is_hot_pick,
)

NOW = datetime(2026, 6, 19, tzinfo=timezone.utc)


def _t(i, *, added_at="2026-06-18T00:00:00Z", popularity=50, source_tags=None,
       current_position=None):
    return CannablissTrack(
        uri=f"spotify:track:{i}",
        name=f"Song {i}",
        artists=f"Artist {i}",
        added_at=added_at,
        source_tags=source_tags or {"master"},
        current_position=current_position,
        popularity=popularity,
        release_date="2026-06-01",
    )


def test_is_hot_pick_checks_top_tracks_only():
    signals = ListeningSignals(top_track_ids=frozenset({"1"}), recently_played_ids=frozenset({"2"}))
    assert _is_hot_pick(_t(1), signals) is True
    assert _is_hot_pick(_t(2), signals) is False


def test_front_score_adds_full_listening_boosts():
    signals = ListeningSignals(
        top_track_ids=frozenset({"1"}), top_tracks_boost=0.3,
        recently_played_ids=frozenset({"1"}), recently_played_boost=0.2,
    )
    base = _front_score(_t(9), ListeningSignals(), NOW)
    boosted = _front_score(_t(1), signals, NOW)
    assert boosted == base + 0.3 + 0.2


def test_body_score_penalizes_hall_and_uses_half_listening():
    signals = ListeningSignals(top_track_ids=frozenset({"1"}), top_tracks_boost=0.4)
    plain = _body_score(_t(9), ListeningSignals(), NOW)
    boosted = _body_score(_t(1), signals, NOW)
    assert boosted == plain + 0.2  # half of 0.4
    hall = _body_score(_t(2, source_tags={"hall"}), ListeningSignals(), NOW)
    assert hall < plain


def test_body_sort_key_orders_lower_position_first_on_ties():
    # Same score inputs; stability tiebreaker prefers the lower current_position.
    a = _t(1, current_position=5)
    b = _t(2, current_position=80)
    key_a = _body_sort_key(a, ListeningSignals(), NOW)
    key_b = _body_sort_key(b, ListeningSignals(), NOW)
    assert key_a > key_b  # reverse=True sort puts a (pos 5) ahead of b (pos 80)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_scoring_helpers.py -v`
Expected: FAIL — `ImportError: cannot import name '_front_score'`.

- [ ] **Step 3: Add constants and helpers**

In `src/cannabliss.py`, replace the old front constants block:

```python
MAJOR_FRONT_QUEUE_DAYS = 21
MAJOR_TOP_10_FRESH_TARGET = 8
MAJOR_TOP_10_CARRYOVER_LIMIT = 2
```

with:

```python
DEFAULT_FRESH_FRONT_SIZE = 15
DEFAULT_FRESH_FRONT_MAX_PER_ARTIST = 2
DEFAULT_REMOVAL_COOLDOWN_DAYS = 7
HALL_BODY_PENALTY = 0.05
```

Then add these helpers (near `_score_track`, which will be removed in Task 6 — keep both for now so existing code still runs):

```python
def _is_hot_pick(track: CannablissTrack, signals: ListeningSignals) -> bool:
    """A song in the playlist that's also in the user's heavy rotation."""
    return track_id(track.uri) in signals.top_track_ids


def _front_score(track: CannablissTrack, signals: ListeningSignals, now: datetime) -> float:
    tid = track_id(track.uri)
    score = _recency_score(track.added_at, now)
    if tid in signals.top_track_ids:
        score += signals.top_tracks_boost
    if tid in signals.recently_played_ids:
        score += signals.recently_played_boost
    return score


def _body_score(track: CannablissTrack, signals: ListeningSignals, now: datetime) -> float:
    tid = track_id(track.uri)
    score = _recency_score(track.added_at, now)
    if tid in signals.top_track_ids:
        score += signals.top_tracks_boost * 0.5
    if tid in signals.recently_played_ids:
        score += signals.recently_played_boost * 0.5
    score += ((track.popularity or 0) / 100.0) * 0.04
    if "hall" in track.source_tags:
        score -= HALL_BODY_PENALTY
    return score


def _front_sort_key(
    track: CannablissTrack,
    signals: ListeningSignals,
    now: datetime,
    weekly_add_ids: set[str],
) -> tuple:
    """Sort key (use reverse=True): hot picks, then weekly adds, then freshness."""
    return (
        1 if _is_hot_pick(track, signals) else 0,
        1 if track.uri in weekly_add_ids else 0,
        _front_score(track, signals, now),
        track.added_at,
        track.name.lower(),
        track.uri,
    )


def _body_sort_key(
    track: CannablissTrack, signals: ListeningSignals, now: datetime
) -> tuple:
    """Sort key (use reverse=True): body score, then stability (lower position first)."""
    return (
        _body_score(track, signals, now),
        -(track.current_position if track.current_position is not None else 10**9),
        track.added_at,
        track.uri,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_scoring_helpers.py -v`
Expected: PASS (4 passed).

Note: removing `MAJOR_*` constants will break references in the current `build_cannabliss_playlist`. That code is fully replaced in Task 6; until then, run only the new test files. To confirm nothing else imports the constants:

Run: `rg -n "MAJOR_TOP_10|MAJOR_FRONT_QUEUE" src tests` — expected: only matches inside `src/cannabliss.py`'s old build body (removed in Task 6).

- [ ] **Step 5: Commit**

```bash
git add src/cannabliss.py tests/test_scoring_helpers.py
git commit -m "feat(cannabliss): add fresh-front detection and body scoring helpers"
```

---

### Task 4: Fresh-front builder

**Files:**
- Modify: `src/cannabliss.py` (add `_build_fresh_front`)
- Test: `tests/test_fresh_front.py` (create)

**Interfaces:**
- Produces: `_build_fresh_front(candidates: list[CannablissTrack], *, weekly_add_ids: set[str], size: int, max_per_artist: int, signals: ListeningSignals, now: datetime) -> list[CannablissTrack]` — sorts by `_front_sort_key` (reverse), enforces `max_per_artist`, returns up to `size` tracks.

- [ ] **Step 1: Write the failing test**

Create `tests/test_fresh_front.py`:

```python
"""Tests for the fresh-front builder."""

from datetime import datetime, timezone

from src.cannabliss import CannablissTrack, ListeningSignals, _build_fresh_front

NOW = datetime(2026, 6, 19, tzinfo=timezone.utc)


def _t(i, *, added_at="2026-06-10T00:00:00Z", artist=None, current_position=None):
    return CannablissTrack(
        uri=f"spotify:track:{i}",
        name=f"Song {i}",
        artists=artist or f"Artist {i}",
        added_at=added_at,
        source_tags={"current"},
        current_position=current_position,
        popularity=50,
        release_date="2026-06-01",
    )


def test_weekly_adds_ordered_newest_first():
    adds = [
        _t(1, added_at="2026-06-15T00:00:00Z"),
        _t(2, added_at="2026-06-18T00:00:00Z"),
        _t(3, added_at="2026-06-12T00:00:00Z"),
    ]
    front = _build_fresh_front(
        adds, weekly_add_ids={t.uri for t in adds}, size=15,
        max_per_artist=2, signals=ListeningSignals(), now=NOW,
    )
    assert [t.uri for t in front] == ["spotify:track:2", "spotify:track:1", "spotify:track:3"]


def test_hot_pick_incumbent_lands_in_top_5_over_fresher_adds():
    adds = [_t(10 + i, added_at=f"2026-06-1{i}T00:00:00Z") for i in range(8)]
    hot_incumbent = _t(999, added_at="2026-01-01T00:00:00Z", current_position=40)
    signals = ListeningSignals(top_track_ids=frozenset({"999"}), top_tracks_boost=0.4)
    front = _build_fresh_front(
        adds + [hot_incumbent], weekly_add_ids={t.uri for t in adds},
        size=15, max_per_artist=2, signals=signals, now=NOW,
    )
    assert hot_incumbent.uri in {t.uri for t in front[:5]}


def test_artist_cap_limits_front_to_two_per_artist():
    binge = [_t(i, artist="Binge Artist", added_at=f"2026-06-1{i}T00:00:00Z") for i in range(7)]
    others = [_t(100 + i, added_at="2026-06-05T00:00:00Z") for i in range(15)]
    front = _build_fresh_front(
        binge + others, weekly_add_ids={t.uri for t in binge},
        size=15, max_per_artist=2, signals=ListeningSignals(), now=NOW,
    )
    binge_in_front = [t for t in front if t.artists == "Binge Artist"]
    assert len(binge_in_front) == 2
    assert len(front) == 15


def test_rolling_fill_tops_up_when_few_weekly_adds():
    adds = [_t(i, added_at="2026-06-18T00:00:00Z") for i in range(8)]
    fill = [_t(200 + i, added_at="2026-06-09T00:00:00Z") for i in range(20)]
    front = _build_fresh_front(
        adds + fill, weekly_add_ids={t.uri for t in adds},
        size=15, max_per_artist=2, signals=ListeningSignals(), now=NOW,
    )
    assert len(front) == 15
    # All 8 weekly adds rank above fill (newer + weekly-add tier).
    assert {t.uri for t in adds} <= {t.uri for t in front[:8]}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_fresh_front.py -v`
Expected: FAIL — `ImportError: cannot import name '_build_fresh_front'`.

- [ ] **Step 3: Implement `_build_fresh_front`**

Add to `src/cannabliss.py`:

```python
def _build_fresh_front(
    candidates: list[CannablissTrack],
    *,
    weekly_add_ids: set[str],
    size: int,
    max_per_artist: int,
    signals: ListeningSignals,
    now: datetime,
) -> list[CannablissTrack]:
    """The top `size` of the playlist: hot picks, then weekly adds, then fill."""
    ordered = sorted(
        _ordered_unique(candidates),
        key=lambda track: _front_sort_key(track, signals, now, weekly_add_ids),
        reverse=True,
    )
    front: list[CannablissTrack] = []
    selected: set[str] = set()
    artist_counts: dict[str, int] = {}
    for track in ordered:
        if len(front) >= size:
            break
        if track.uri in selected:
            continue
        artist = _primary_artist(track.artists)
        if artist_counts.get(artist, 0) >= max_per_artist:
            continue
        selected.add(track.uri)
        artist_counts[artist] = artist_counts.get(artist, 0) + 1
        front.append(track)
    return front
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_fresh_front.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/cannabliss.py tests/test_fresh_front.py
git commit -m "feat(cannabliss): add fresh-front builder (tiered sort + artist cap)"
```

---

### Task 5: Body builder

**Files:**
- Modify: `src/cannabliss.py` (add `_build_body`)
- Test: `tests/test_body_builder.py` (create)

**Interfaces:**
- Produces: `_build_body(*, protected_overflow, candidates, slots, max_per_artist, front_tracks, signals, now) -> list[CannablissTrack]` — places `protected_overflow` first (exempt from the cap), then fills up to `slots` total from `candidates` (sorted by `_body_sort_key` reverse) respecting `max_per_artist`. Artist counts are seeded from `front_tracks` + `protected_overflow`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_body_builder.py`:

```python
"""Tests for the body builder."""

from datetime import datetime, timezone

from src.cannabliss import CannablissTrack, ListeningSignals, _build_body

NOW = datetime(2026, 6, 19, tzinfo=timezone.utc)


def _t(i, *, added_at="2026-01-01T00:00:00Z", artist=None, current_position=None,
       popularity=50, source_tags=None):
    return CannablissTrack(
        uri=f"spotify:track:{i}",
        name=f"Song {i}",
        artists=artist or f"Artist {i}",
        added_at=added_at,
        source_tags=source_tags or {"current", "master"},
        current_position=current_position,
        popularity=popularity,
        release_date="2024-01-01",
    )


def test_protected_overflow_sits_at_top_of_body():
    protected = [_t(1, added_at="2026-06-18T00:00:00Z")]
    candidates = [_t(100 + i, current_position=i + 1) for i in range(10)]
    body = _build_body(
        protected_overflow=protected, candidates=candidates, slots=6,
        max_per_artist=2, front_tracks=[], signals=ListeningSignals(), now=NOW,
    )
    assert body[0].uri == "spotify:track:1"
    assert len(body) == 6


def test_incumbents_hold_relative_order_on_score_ties():
    # Uniform added_at + no listening => same body_score; stability tiebreaker decides.
    candidates = [
        _t(1, current_position=80),
        _t(2, current_position=10),
        _t(3, current_position=45),
    ]
    body = _build_body(
        protected_overflow=[], candidates=candidates, slots=3,
        max_per_artist=2, front_tracks=[], signals=ListeningSignals(), now=NOW,
    )
    assert [t.uri for t in body] == ["spotify:track:2", "spotify:track:3", "spotify:track:1"]


def test_body_respects_artist_cap_seeded_from_front():
    front = [_t(1, artist="Repeat"), _t(2, artist="Repeat")]  # already 2 in the front
    candidates = [_t(3, artist="Repeat", current_position=5), _t(4, artist="Other", current_position=6)]
    body = _build_body(
        protected_overflow=[], candidates=candidates, slots=5,
        max_per_artist=2, front_tracks=front, signals=ListeningSignals(), now=NOW,
    )
    assert "spotify:track:3" not in {t.uri for t in body}  # Repeat already at cap via front
    assert "spotify:track:4" in {t.uri for t in body}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_body_builder.py -v`
Expected: FAIL — `ImportError: cannot import name '_build_body'`.

- [ ] **Step 3: Implement `_build_body`**

Add to `src/cannabliss.py`:

```python
def _build_body(
    *,
    protected_overflow: list[CannablissTrack],
    candidates: list[CannablissTrack],
    slots: int,
    max_per_artist: int,
    front_tracks: list[CannablissTrack],
    signals: ListeningSignals,
    now: datetime,
) -> list[CannablissTrack]:
    """Body = protected overflow first, then freshness-ordered fill up to `slots`."""
    body: list[CannablissTrack] = []
    selected: set[str] = set()
    artist_counts: dict[str, int] = {}

    for track in front_tracks:
        artist = _primary_artist(track.artists)
        artist_counts[artist] = artist_counts.get(artist, 0) + 1

    for track in protected_overflow:
        if track.uri in selected:
            continue
        selected.add(track.uri)
        artist = _primary_artist(track.artists)
        artist_counts[artist] = artist_counts.get(artist, 0) + 1
        body.append(track)

    ordered = sorted(
        _ordered_unique(candidates),
        key=lambda track: _body_sort_key(track, signals, now),
        reverse=True,
    )
    for track in ordered:
        if len(body) >= max(0, slots):
            break
        if track.uri in selected:
            continue
        artist = _primary_artist(track.artists)
        if artist_counts.get(artist, 0) >= max_per_artist:
            continue
        selected.add(track.uri)
        artist_counts[artist] = artist_counts.get(artist, 0) + 1
        body.append(track)
    return body
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_body_builder.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/cannabliss.py tests/test_body_builder.py
git commit -m "feat(cannabliss): add body builder (protected-first, stable, artist-capped)"
```

---

### Task 6: Rewrite `build_cannabliss_playlist`

**Files:**
- Modify: `src/cannabliss.py` (`CannablissBuildResult`, `build_cannabliss_playlist`; delete `_score_track`, `_tail_strength`, `_prune_tail_candidates`, `_interleave_tracks`, `_front_queue_candidates`, `_plan_batch`, `_fill_zone`, `_select_scored`, `_top_ranked` if now unused — verify with `rg`)
- Test: `tests/test_cannabliss.py` (replace obsolete tests; add fresh-front integration tests)

**Interfaces:**
- Consumes: `_build_fresh_front`, `_build_body`, `_is_hot_pick`, `merge_track_sets`, `_dedupe_song_variants`, `_ordered_unique`, `_primary_artist`, `track_id`, constants from Task 3.
- Produces (new/changed signature):

```python
def build_cannabliss_playlist(
    *,
    master_tracks, current_tracks, feeder_tracks, hall_tracks,
    target_size, weekly_insertions,
    update_mode="major", micro_refresh_count=5,
    max_tracks_per_artist=2,
    listening_signals=None,
    previous_track_uris=frozenset(),     # NEW
    cooldown_uris=frozenset(),           # NEW
    fresh_front_size=DEFAULT_FRESH_FRONT_SIZE,                      # NEW
    fresh_front_max_per_artist=DEFAULT_FRESH_FRONT_MAX_PER_ARTIST,  # NEW
    now=None,
) -> CannablissBuildResult
```

  - `CannablissBuildResult` gains `removed_uris: list[str] = field(default_factory=list)`.
  - `result.zones` keys are exactly `"fresh_front"` and `"body"`.

> **Note:** `max_hall_returns` is removed from the signature (no caller passes it; Hall is now just a penalized source). Confirm with `rg -n "max_hall_returns" src tests` before editing — expected: only the old definition.

- [ ] **Step 1: Add `removed_uris` to the result dataclass**

In `src/cannabliss.py`, update:

```python
@dataclass
class CannablissBuildResult:
    ordered_tracks: list[CannablissTrack]
    zones: dict[str, list[CannablissTrack]]
    summary: dict[str, list[str]]
    new_track_count: int
    update_mode: str
    removed_uris: list[str] = field(default_factory=list)
```

- [ ] **Step 2: Write the new integration tests (replace the file body)**

Replace the entire contents of `tests/test_cannabliss.py` with the following. (The old tests assert removed behavior — five zones, 8-fresh top-10, front_queue — and are intentionally dropped.)

```python
"""Tests for Cannabliss curated playlist construction (fresh-front model)."""

from datetime import datetime, timezone

from src.cannabliss import CannablissTrack, ListeningSignals, build_cannabliss_playlist


def _track(i, *, source_tags=None, added_at="2026-06-01T00:00:00Z",
           current_position=None, popularity=50, release_date="2026-06-01", artist=None):
    return CannablissTrack(
        uri=f"spotify:track:{i}",
        name=f"Song {i}",
        artists=artist or f"Artist {i}",
        added_at=added_at,
        source_tags=source_tags or {"master"},
        current_position=current_position,
        popularity=popularity,
        release_date=release_date,
    )


NOW = datetime(2026, 6, 19, tzinfo=timezone.utc)


def _existing_playlist(n, *, added_at="2026-06-12T00:00:00Z"):
    """A live playlist of `n` tracks the engine wrote last run (uniform added_at)."""
    return [
        _track(i, source_tags={"current", "master"}, added_at=added_at,
               current_position=i + 1, artist=f"Current Artist {i}")
        for i in range(n)
    ]


def test_weekly_adds_become_the_front_newest_first():
    current = _existing_playlist(100)
    adds = [
        _track(900 + k, source_tags={"current"}, current_position=100 + k,
               added_at=f"2026-06-{14 + k:02d}T00:00:00Z", artist=f"Add Artist {k}")
        for k in range(4)
    ]
    prev = {t.uri for t in current}
    result = build_cannabliss_playlist(
        master_tracks=current + adds,
        current_tracks=current + adds,
        feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25,
        previous_track_uris=prev, now=NOW,
    )
    front_uris = [t.uri for t in result.zones["fresh_front"]]
    # Newest add (k=3, 2026-06-17) leads.
    assert front_uris[0] == "spotify:track:903"
    assert {t.uri for t in adds} <= set(front_uris)
    assert len(result.ordered_tracks) == 100


def test_hot_pick_add_lands_in_top_5():
    current = _existing_playlist(100)
    plain_adds = [
        _track(900 + k, source_tags={"current"}, current_position=100 + k,
               added_at=f"2026-06-{16 + 0:02d}T00:00:00Z", artist=f"Add Artist {k}")
        for k in range(6)
    ]
    hot_add = _track(950, source_tags={"current"}, current_position=120,
                     added_at="2026-06-14T00:00:00Z", artist="Hot Artist")
    prev = {t.uri for t in current}
    result = build_cannabliss_playlist(
        master_tracks=current + plain_adds + [hot_add],
        current_tracks=current + plain_adds + [hot_add],
        feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25,
        previous_track_uris=prev,
        listening_signals=ListeningSignals(top_track_ids=frozenset({"950"}), top_tracks_boost=0.4),
        now=NOW,
    )
    top_5 = {t.uri for t in result.ordered_tracks[:5]}
    assert hot_add.uri in top_5


def test_rolling_fill_when_fewer_than_fifteen_adds():
    current = _existing_playlist(100, added_at="2026-06-05T00:00:00Z")
    adds = [
        _track(900 + k, source_tags={"current"}, current_position=100 + k,
               added_at="2026-06-18T00:00:00Z", artist=f"Add Artist {k}")
        for k in range(8)
    ]
    prev = {t.uri for t in current}
    result = build_cannabliss_playlist(
        master_tracks=current + adds, current_tracks=current + adds,
        feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25,
        previous_track_uris=prev, fresh_front_size=15, now=NOW,
    )
    front = result.zones["fresh_front"]
    assert len(front) == 15
    assert {t.uri for t in adds} <= {t.uri for t in front[:8]}


def test_artist_binge_capped_in_front_but_all_kept():
    current = _existing_playlist(100, added_at="2026-06-05T00:00:00Z")
    binge = [
        _track(900 + k, source_tags={"current"}, current_position=100 + k,
               added_at=f"2026-06-{12 + k:02d}T00:00:00Z", artist="Binge Artist")
        for k in range(6)
    ]
    prev = {t.uri for t in current}
    result = build_cannabliss_playlist(
        master_tracks=current + binge, current_tracks=current + binge,
        feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25,
        previous_track_uris=prev, fresh_front_max_per_artist=2, now=NOW,
    )
    front_binge = [t for t in result.zones["fresh_front"] if t.artists == "Binge Artist"]
    assert len(front_binge) == 2
    kept = {t.uri for t in result.ordered_tracks}
    assert {t.uri for t in binge} <= kept  # none discarded


def test_protected_adds_survive_trim_and_oldest_retire():
    current = _existing_playlist(100, added_at="2026-06-12T00:00:00Z")
    # 20 weekly adds push the playlist to 120; trim back to 100 must keep the adds.
    adds = [
        _track(900 + k, source_tags={"current"}, current_position=100 + k,
               added_at="2026-06-18T00:00:00Z", artist=f"Add Artist {k}")
        for k in range(20)
    ]
    prev = {t.uri for t in current}
    result = build_cannabliss_playlist(
        master_tracks=current + adds, current_tracks=current + adds,
        feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25,
        previous_track_uris=prev, now=NOW,
    )
    kept = {t.uri for t in result.ordered_tracks}
    assert {t.uri for t in adds} <= kept
    assert len(result.ordered_tracks) == 100
    assert len(result.removed_uris) >= 20  # 20 oldest incumbents retired


def test_cooldown_excludes_removed_song_from_refill():
    current = _existing_playlist(60, added_at="2026-06-12T00:00:00Z")
    benched = _track(7777, source_tags={"master"}, added_at="2026-06-18T00:00:00Z")
    prev = {t.uri for t in current}
    result = build_cannabliss_playlist(
        master_tracks=current + [benched], current_tracks=current,
        feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25,
        previous_track_uris=prev, cooldown_uris={benched.uri}, now=NOW,
    )
    assert benched.uri not in {t.uri for t in result.ordered_tracks}


def test_cooldown_overridden_by_manual_readd():
    current = _existing_playlist(60, added_at="2026-06-12T00:00:00Z")
    readded = _track(7777, source_tags={"current"}, current_position=61,
                     added_at="2026-06-18T00:00:00Z")
    prev = {t.uri for t in current}  # readded is NOT in prev => it's a weekly add
    result = build_cannabliss_playlist(
        master_tracks=current + [readded], current_tracks=current + [readded],
        feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25,
        previous_track_uris=prev, cooldown_uris={readded.uri}, now=NOW,
    )
    assert readded.uri in {t.uri for t in result.ordered_tracks[:15]}


def test_user_removed_song_recorded_for_cooldown():
    current = _existing_playlist(100, added_at="2026-06-12T00:00:00Z")
    # Race deleted a track during the week: it's in the previous run but no longer
    # in the live playlist (id 500 is outside the 0..99 range of `current`).
    deleted_uri = "spotify:track:500"
    prev = {t.uri for t in current} | {deleted_uri}
    result = build_cannabliss_playlist(
        master_tracks=current, current_tracks=current,
        feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25,
        previous_track_uris=prev, now=NOW,
    )
    assert deleted_uri in result.removed_uris


def test_hall_track_sits_below_equivalent_non_hall_in_body():
    # Fresh incumbents fill the front, so hall + plain land in the body where the
    # Hall penalty applies. plain has the *lower* uri, so only the penalty can
    # explain plain ranking above hall (uri tiebreak alone would favor hall).
    current = _existing_playlist(20, added_at="2026-06-18T00:00:00Z")
    plain = _track(8000, source_tags={"master"}, added_at="2026-06-01T00:00:00Z", popularity=50)
    hall = _track(8001, source_tags={"hall"}, added_at="2026-06-01T00:00:00Z", popularity=50)
    prev = {t.uri for t in current}
    result = build_cannabliss_playlist(
        master_tracks=current + [plain, hall],
        current_tracks=current,
        feeder_tracks=[], hall_tracks=[hall],
        target_size=100, weekly_insertions=25,
        previous_track_uris=prev, now=NOW,
    )
    order = [t.uri for t in result.ordered_tracks]
    assert order.index(plain.uri) < order.index(hall.uri)


def test_zones_are_two_tiers_partitioning_the_playlist():
    current = _existing_playlist(100, added_at="2026-06-12T00:00:00Z")
    prev = {t.uri for t in current}
    result = build_cannabliss_playlist(
        master_tracks=current, current_tracks=current,
        feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25,
        previous_track_uris=prev, now=NOW,
    )
    assert set(result.zones.keys()) == {"fresh_front", "body"}
    combined = [t.uri for t in result.zones["fresh_front"]] + [t.uri for t in result.zones["body"]]
    assert combined == [t.uri for t in result.ordered_tracks]


def test_micro_promotes_adds_and_preserves_everything():
    current = _existing_playlist(100, added_at="2026-06-12T00:00:00Z")
    adds = [
        _track(900 + k, source_tags={"current"}, current_position=100 + k,
               added_at="2026-06-18T00:00:00Z", artist=f"Add Artist {k}")
        for k in range(3)
    ]
    new_master = [
        _track(3000 + k, source_tags={"master"}, added_at="2026-06-17T00:00:00Z",
               artist=f"New Artist {k}")
        for k in range(10)
    ]
    prev = {t.uri for t in current}
    result = build_cannabliss_playlist(
        master_tracks=current + adds + new_master,
        current_tracks=current + adds,
        feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25,
        update_mode="micro", micro_refresh_count=5,
        previous_track_uris=prev, now=NOW,
    )
    # All current tracks preserved (no retirement in micro).
    assert {t.uri for t in current + adds} <= {t.uri for t in result.ordered_tracks}
    assert result.removed_uris == []
    # Weekly adds promoted to the front.
    assert {t.uri for t in adds} <= {t.uri for t in result.zones["fresh_front"]}


def test_initial_build_hits_target_size_from_master():
    master = [
        _track(i, added_at=f"2026-06-{(i % 28) + 1:02d}T00:00:00Z", artist=f"Artist {i}")
        for i in range(220)
    ]
    result = build_cannabliss_playlist(
        master_tracks=master, current_tracks=[],
        feeder_tracks=[], hall_tracks=[],
        target_size=100, weekly_insertions=25, now=NOW,
    )
    assert len(result.ordered_tracks) == 100
    assert len(result.zones["fresh_front"]) == 15
    assert len(result.zones["body"]) == 85
```

- [ ] **Step 3: Run the new tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cannabliss.py -v`
Expected: FAIL — the current build function still produces five-zone output / old signature errors (`unexpected keyword argument 'previous_track_uris'`).

- [ ] **Step 4: Replace `build_cannabliss_playlist` with the new orchestrator**

In `src/cannabliss.py`, replace the entire `build_cannabliss_playlist` function body with:

```python
def build_cannabliss_playlist(
    *,
    master_tracks: list[CannablissTrack],
    current_tracks: list[CannablissTrack],
    feeder_tracks: list[CannablissTrack],
    hall_tracks: list[CannablissTrack],
    target_size: int,
    weekly_insertions: int,
    update_mode: str = "major",
    micro_refresh_count: int = 5,
    max_tracks_per_artist: int = 2,
    listening_signals: ListeningSignals | None = None,
    previous_track_uris: frozenset[str] | set[str] = frozenset(),
    cooldown_uris: frozenset[str] | set[str] = frozenset(),
    fresh_front_size: int = DEFAULT_FRESH_FRONT_SIZE,
    fresh_front_max_per_artist: int = DEFAULT_FRESH_FRONT_MAX_PER_ARTIST,
    now: datetime | None = None,
) -> CannablissBuildResult:
    """Build the ordered Cannabliss playlist around the user's recent hand-adds."""
    current = now or datetime.now(timezone.utc)
    signals = listening_signals or ListeningSignals()
    cooldown = set(cooldown_uris)
    prev = set(previous_track_uris)

    merged = _dedupe_song_variants(
        merge_track_sets([master_tracks, current_tracks, feeder_tracks, hall_tracks])
    )
    current_order = [
        track.uri for track in sorted(current_tracks, key=lambda t: t.current_position or 10**9)
    ]
    current_ids = set(current_order)

    # Weekly adds: songs now in the playlist that weren't in the previous run.
    # With no baseline (true first run), treat all current as incumbents.
    weekly_add_ids = {uri for uri in current_order if uri not in prev} if prev else set()
    weekly_adds = [merged[uri] for uri in current_order if uri in weekly_add_ids and uri in merged]
    incumbents = [
        merged[uri]
        for uri in current_order
        if uri in merged and uri not in weekly_add_ids
    ]
    # Fill candidates: not already in the playlist, not benched (manual re-adds override cooldown).
    fill_candidates = [
        track
        for uri, track in merged.items()
        if uri not in current_ids and uri not in cooldown
    ]

    hot_incumbents = [track for track in incumbents if _is_hot_pick(track, signals)]

    if update_mode == "micro" and current_order:
        # Micro: the front is drawn ONLY from songs already in the playlist
        # (promote weekly adds + hot picks, fill from incumbents). New tracks
        # enter solely via the capped new_fill below, so micro stays gentle.
        front = _build_fresh_front(
            _ordered_unique(weekly_adds + hot_incumbents + incumbents),
            weekly_add_ids=weekly_add_ids,
            size=fresh_front_size,
            max_per_artist=fresh_front_max_per_artist,
            signals=signals,
            now=current,
        )
        front_ids = {track.uri for track in front}
        remaining = [
            merged[uri]
            for uri in current_order
            if uri in merged and uri not in front_ids
        ]
        seen = front_ids | {track.uri for track in remaining}
        new_fill = _select_simple(
            sorted(
                fill_candidates,
                key=lambda t: _front_sort_key(t, signals, current, weekly_add_ids),
                reverse=True,
            ),
            limit=micro_refresh_count,
            seen=seen,
            max_per_artist=max_tracks_per_artist,
        )
        body = remaining + new_fill
        ordered = front + body
    else:
        # Major / initial: rolling fill may pull fresh Master/feeder into the front.
        front = _build_fresh_front(
            _ordered_unique(weekly_adds + hot_incumbents + incumbents + fill_candidates),
            weekly_add_ids=weekly_add_ids,
            size=fresh_front_size,
            max_per_artist=fresh_front_max_per_artist,
            signals=signals,
            now=current,
        )
        front_ids = {track.uri for track in front}
        protected_overflow = [track for track in weekly_adds if track.uri not in front_ids]
        protected_ids = front_ids | {track.uri for track in protected_overflow}
        body_candidates = [
            track
            for track in (incumbents + fill_candidates)
            if track.uri not in protected_ids
        ]
        slots = target_size - len(front)
        body = _build_body(
            protected_overflow=protected_overflow,
            candidates=body_candidates,
            slots=slots,
            max_per_artist=max_tracks_per_artist,
            front_tracks=front,
            signals=signals,
            now=current,
        )
        ordered = front + body

    ordered_ids = {track.uri for track in ordered}
    baseline = current_ids | prev
    removed_uris = [uri for uri in baseline if uri not in ordered_ids]

    summary = _build_summary(
        ordered=ordered,
        current_order=current_order,
        current_ids=current_ids,
        front=front,
        update_mode=update_mode,
        weekly_insertions=weekly_insertions,
        micro_refresh_count=micro_refresh_count,
    )

    return CannablissBuildResult(
        ordered_tracks=ordered,
        zones={"fresh_front": front, "body": body},
        summary=summary,
        new_track_count=sum(1 for track in ordered if track.uri not in current_ids),
        update_mode=update_mode,
        removed_uris=removed_uris,
    )
```

- [ ] **Step 5: Add the two small support functions used above**

Add to `src/cannabliss.py`:

```python
def _select_simple(
    tracks: list[CannablissTrack],
    *,
    limit: int,
    seen: set[str],
    max_per_artist: int,
) -> list[CannablissTrack]:
    """Pick up to `limit` unseen tracks, capping per primary artist."""
    chosen: list[CannablissTrack] = []
    artist_counts: dict[str, int] = {}
    for track in tracks:
        if len(chosen) >= max(0, limit):
            break
        if track.uri in seen:
            continue
        artist = _primary_artist(track.artists)
        if artist_counts.get(artist, 0) >= max_per_artist:
            continue
        seen.add(track.uri)
        artist_counts[artist] = artist_counts.get(artist, 0) + 1
        chosen.append(track)
    return chosen


def _build_summary(
    *,
    ordered: list[CannablissTrack],
    current_order: list[str],
    current_ids: set[str],
    front: list[CannablissTrack],
    update_mode: str,
    weekly_insertions: int,
    micro_refresh_count: int,
) -> dict[str, list[str]]:
    positions_before = {uri: index for index, uri in enumerate(current_order, start=1)}
    positions_after = {track.uri: index for index, track in enumerate(ordered, start=1)}
    front_before = current_order[:len(front)]
    front_after = [track.uri for track in front]

    summary = {
        "update_mode": [update_mode],
        "added": [track_id(t.uri) for t in ordered if t.uri not in current_ids],
        "promoted": [
            track_id(uri) for uri, old in positions_before.items()
            if uri in positions_after and positions_after[uri] < old
        ],
        "held": [
            track_id(uri) for uri, old in positions_before.items()
            if uri in positions_after and positions_after[uri] == old
        ],
        "shifted_down": [
            track_id(uri) for uri, old in positions_before.items()
            if uri in positions_after and positions_after[uri] > old
        ],
        "removed": [track_id(uri) for uri in current_order if uri not in positions_after],
        "fresh_front_added": [
            track_id(uri) for uri in front_after if uri not in set(front_before)
        ],
        "retained": [track_id(uri) for uri in current_order if uri in positions_after],
    }
    total_changed = len(set(summary["added"] + summary["removed"] + summary["promoted"]))
    summary["total_changed"] = [str(total_changed)]
    if update_mode == "micro":
        summary["micro_adjustments"] = [str(min(total_changed, micro_refresh_count))]
    return summary
```

- [ ] **Step 6: Delete the now-dead old helpers**

Confirm they are unused, then delete from `src/cannabliss.py`: `_select_scored`, `_plan_batch`, `_fill_zone`, `_top_ranked`, `_front_queue_candidates`, `_prune_tail_candidates`, `_tail_strength`, `_score_track`, `_interleave_tracks`.

Run: `rg -n "_select_scored|_plan_batch|_fill_zone|_top_ranked|_front_queue_candidates|_prune_tail_candidates|_tail_strength|_score_track|_interleave_tracks" src tests`
Expected after deletion: no matches. (Keep `_recency_score`, `_release_bias` is now only used by deleted code — check: `rg -n "_release_bias" src` → if no remaining users, delete it too. `_recency_score` is still used by `_front_score`/`_body_score`; keep it.)

- [ ] **Step 7: Run the full suite**

Run: `.venv/bin/python -m pytest tests/test_cannabliss.py -v`
Expected: PASS (all new cases green).

Run: `.venv/bin/python -m pytest -q`
Expected: PASS overall (test_main may still need Task 7 wiring — if test_main fails on the new signature, that is fixed in Task 7; note it and proceed).

- [ ] **Step 8: Commit**

```bash
git add src/cannabliss.py tests/test_cannabliss.py
git commit -m "feat(cannabliss): rewrite build around weekly hand-adds; collapse to two tiers"
```

---

### Task 7: Wire `main.py` + persist cooldown in state

**Files:**
- Modify: `src/main.py` (compute `now`, derive `previous_track_uris` + active cooldown, pass new kwargs, drop `front_queue` from the print labels)
- Modify: `src/cannabliss.py` (`append_cannabliss_run` also prunes/merges cooldown)
- Test: `tests/test_state_cooldown.py` (create); check `tests/test_main.py`

**Interfaces:**
- Consumes: `active_cooldown_uris`, `merge_cooldown` (Task 2); `CannablissBuildResult.removed_uris` (Task 6).
- Produces:
  - `append_cannabliss_run(result, *, path=..., now=None, cooldown_days=DEFAULT_REMOVAL_COOLDOWN_DAYS)` — appends the run AND writes `payload["cooldown"] = merge_cooldown(existing, result.removed_uris, now, days=cooldown_days)`.
  - `previous_run_track_uris(state) -> set[str]` — URIs from the most recent run's `track_ids` (reconstructed as `spotify:track:<id>`), empty if none.

- [ ] **Step 1: Write the failing test**

Create `tests/test_state_cooldown.py`:

```python
"""Tests for run-state cooldown persistence + previous-run URI reconstruction."""

from datetime import datetime, timezone

from src.cannabliss import (
    CannablissBuildResult,
    append_cannabliss_run,
    load_cannabliss_state,
    previous_run_track_uris,
)

NOW = datetime(2026, 6, 19, tzinfo=timezone.utc)


def _result(track_ids, removed_uris):
    tracks = []  # ordered_tracks not needed for these assertions
    return CannablissBuildResult(
        ordered_tracks=tracks,
        zones={"fresh_front": [], "body": []},
        summary={"track_ids_for_test": track_ids},
        new_track_count=0,
        update_mode="major",
        removed_uris=removed_uris,
    )


def test_previous_run_track_uris_reconstructs_uris():
    state = {"runs": [{"timestamp": "t", "track_ids": ["aaa", "bbb"]}]}
    assert previous_run_track_uris(state) == {"spotify:track:aaa", "spotify:track:bbb"}


def test_previous_run_track_uris_empty_when_no_runs():
    assert previous_run_track_uris({"runs": []}) == set()


def test_append_run_records_cooldown(tmp_path):
    path = str(tmp_path / "state.json")
    result = CannablissBuildResult(
        ordered_tracks=[], zones={"fresh_front": [], "body": []},
        summary={}, new_track_count=0, update_mode="major",
        removed_uris=["spotify:track:gone"],
    )
    append_cannabliss_run(result, path=path, now=NOW, cooldown_days=7)
    state = load_cannabliss_state(path)
    assert [e["uri"] for e in state["cooldown"]] == ["spotify:track:gone"]
    assert state["cooldown"][0]["removed_at"] == NOW.isoformat()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_state_cooldown.py -v`
Expected: FAIL — `ImportError: cannot import name 'previous_run_track_uris'`.

- [ ] **Step 3: Implement `previous_run_track_uris` and update `append_cannabliss_run`**

In `src/cannabliss.py`, add:

```python
def previous_run_track_uris(state: dict) -> set[str]:
    """URIs (`spotify:track:<id>`) of the most recent recorded run, or empty."""
    runs = state.get("runs") or []
    if not runs:
        return set()
    return {f"spotify:track:{tid}" for tid in runs[-1].get("track_ids", []) if tid}
```

Replace `append_cannabliss_run` with:

```python
def append_cannabliss_run(
    result: CannablissBuildResult,
    *,
    path: str = "data/cannabliss_state.json",
    now: datetime | None = None,
    cooldown_days: int = DEFAULT_REMOVAL_COOLDOWN_DAYS,
) -> None:
    stamp = now or datetime.now(timezone.utc)
    payload = load_cannabliss_state(path)
    runs = payload.setdefault("runs", [])
    runs.append(
        {
            "timestamp": stamp.isoformat(),
            "track_ids": [track_id(t.uri) for t in result.ordered_tracks],
            "new_track_count": result.new_track_count,
            "summary": result.summary,
            "zones": {
                zone: [track_id(t.uri) for t in tracks]
                for zone, tracks in result.zones.items()
            },
        }
    )
    payload["cooldown"] = merge_cooldown(
        payload.get("cooldown", []), result.removed_uris, stamp, days=cooldown_days
    )
    save_cannabliss_state(payload, path)
```

- [ ] **Step 4: Run the state test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_state_cooldown.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Wire `main.py`**

In `src/main.py`, inside `run_cannabliss`, replace the state-load + build + print + append section. Specifically:

Replace:

```python
    state = load_cannabliss_state(cfg.cannabliss_state_path)
    print(f"🧾 Loaded Cannabliss state with {len(state.get('runs', []))} prior runs")

    result = build_cannabliss_playlist(
        master_tracks=parse_source_items(master_items, source_tag="master"),
        current_tracks=parse_source_items(current_items, source_tag="current", current_order=True),
        feeder_tracks=feeder_tracks,
        hall_tracks=parse_source_items(hall_items, source_tag="hall"),
        target_size=cfg.cannabliss_target_size,
        weekly_insertions=cfg.cannabliss_weekly_insertions,
        update_mode=cfg.cannabliss_update_mode,
        micro_refresh_count=cfg.cannabliss_micro_refresh_count,
        max_tracks_per_artist=cfg.max_tracks_per_artist,
        listening_signals=ListeningSignals(
            top_track_ids=frozenset(top_track_ids),
            recently_played_ids=frozenset(recently_played_ids),
            top_tracks_boost=cfg.cannabliss_top_tracks_boost,
            recently_played_boost=cfg.cannabliss_recently_played_boost,
        ),
    )
```

with:

```python
    from datetime import datetime, timezone
    from src.cannabliss import active_cooldown_uris, previous_run_track_uris

    now = datetime.now(timezone.utc)
    state = load_cannabliss_state(cfg.cannabliss_state_path)
    print(f"🧾 Loaded Cannabliss state with {len(state.get('runs', []))} prior runs")

    previous_uris = previous_run_track_uris(state)
    cooldown_uris = active_cooldown_uris(
        state.get("cooldown", []), now, days=cfg.cannabliss_removal_cooldown_days
    )
    print(
        f"🧊 {len(previous_uris)} tracks in last run; "
        f"{len(cooldown_uris)} benched by cooldown"
    )

    result = build_cannabliss_playlist(
        master_tracks=parse_source_items(master_items, source_tag="master"),
        current_tracks=parse_source_items(current_items, source_tag="current", current_order=True),
        feeder_tracks=feeder_tracks,
        hall_tracks=parse_source_items(hall_items, source_tag="hall"),
        target_size=cfg.cannabliss_target_size,
        weekly_insertions=cfg.cannabliss_weekly_insertions,
        update_mode=cfg.cannabliss_update_mode,
        micro_refresh_count=cfg.cannabliss_micro_refresh_count,
        max_tracks_per_artist=cfg.max_tracks_per_artist,
        listening_signals=ListeningSignals(
            top_track_ids=frozenset(top_track_ids),
            recently_played_ids=frozenset(recently_played_ids),
            top_tracks_boost=cfg.cannabliss_top_tracks_boost,
            recently_played_boost=cfg.cannabliss_recently_played_boost,
        ),
        previous_track_uris=previous_uris,
        cooldown_uris=cooldown_uris,
        fresh_front_size=cfg.cannabliss_fresh_front_size,
        fresh_front_max_per_artist=cfg.cannabliss_fresh_front_max_per_artist,
        now=now,
    )
```

- [ ] **Step 6: Update the print labels and the append call**

In `src/main.py`, change the labels loop — replace:

```python
        "top_10_added",
        "top_10_removed",
        "top_20_added",
        "top_20_removed",
        "front_queue",
```

with:

```python
        "fresh_front_added",
```

And replace:

```python
    append_cannabliss_run(result, path=cfg.cannabliss_state_path)
```

with:

```python
    append_cannabliss_run(
        result,
        path=cfg.cannabliss_state_path,
        now=now,
        cooldown_days=cfg.cannabliss_removal_cooldown_days,
    )
```

- [ ] **Step 7: Run the full suite + a dry run**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS. If `tests/test_main.py` referenced the old summary labels or signature, update those assertions to the new labels (`fresh_front_added`) / two-tier zones — show no `front_queue`/`top_10_*` keys are required.

Run (manual, optional, needs env): `DRY_RUN=1 python -m src.main` — expected: prints a fresh-front preview and "DRY RUN — no changes" with no traceback.

- [ ] **Step 8: Commit**

```bash
git add src/main.py src/cannabliss.py tests/test_state_cooldown.py tests/test_main.py
git commit -m "feat(cannabliss): wire previous-run + cooldown through main and state"
```

---

### Task 8: Update the workflow YAMLs

**Files:**
- Modify: `.github/workflows/weekly.yml`
- Modify: `.github/workflows/cannabliss-micro.yml`

**Interfaces:** none (config passthrough).

- [ ] **Step 1: Add the env vars to `weekly.yml`**

In `.github/workflows/weekly.yml`, under the `env:` block of the run step, add (after `MAX_TRACKS_PER_ARTIST: "2"`):

```yaml
          CANNABLISS_FRESH_FRONT_SIZE: "15"
          CANNABLISS_FRESH_FRONT_MAX_PER_ARTIST: "2"
          CANNABLISS_REMOVAL_COOLDOWN_DAYS: "7"
```

- [ ] **Step 2: Add the same three lines to `cannabliss-micro.yml`**

In `.github/workflows/cannabliss-micro.yml`, under its run-step `env:` block, add the identical three lines (place them after `CANNABLISS_RECENTLY_PLAYED_BOOST: "0.25"`).

- [ ] **Step 3: Validate YAML parses**

Run: `python -c "import yaml,sys; [yaml.safe_load(open(p)) for p in ['.github/workflows/weekly.yml','.github/workflows/cannabliss-micro.yml']]; print('ok')"`
Expected: `ok`. (If `yaml` is unavailable, skip — the values mirror Task 1 defaults.)

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/weekly.yml .github/workflows/cannabliss-micro.yml
git commit -m "chore(ci): pass fresh-front config to both workflows"
```

---

### Task 9: Update docs (dashboard map, README, philosophy)

**Files:**
- Modify: `data/dashboard/liveSpotify.ts:96-102` (zone map)
- Modify: `README.md:181-198` (Cannabliss Model section)
- Modify: `docs/cannabliss-philosophy.md` (Playlist Structure + Premium tier)

**Interfaces:** none.

- [ ] **Step 1: Update the dashboard zone map**

In `data/dashboard/liveSpotify.ts`, replace the `zoneConfig` array (lines ~96–102):

```ts
const zoneConfig = [
  { key: "fresh_front", zoneId: "fresh", name: "Fresh Front", range: "1-15" },
  { key: "body", zoneId: "body", name: "Body", range: "16-100" },
] as const;
```

- [ ] **Step 2: Update the README Cannabliss Model section**

In `README.md`, replace the "Cannabliss Model" body (lines ~183–198) with:

```markdown
Cannabliss is built around the songs Race hand-adds to the public playlist:
- `1–15`: **Fresh front** — the songs added since the last run, newest first.
  Songs that are also in heavy rotation land in the top 5; at most 2 per artist.
- `16–100`: **Body** — everything else, ordered by add-recency (with a light
  listening + popularity nudge), holding a stable order week to week.

Major (Friday) refreshes rebuild the list and trim back to 100, retiring the
oldest tracks; hand-adds are protected from that trim. Micro (Mon/Wed) refreshes
promote the week's adds to the front and preserve everything else. A song that
was removed (retired or deleted) is benched for a week before it can return.
```

- [ ] **Step 3: Update the philosophy doc**

In `docs/cannabliss-philosophy.md`, replace the "## Playlist Structure" section through the end of the "### 41-50: Interleaved Stabilizers" subsection with:

```markdown
## Playlist Structure

Cannabliss has two tiers, driven by the curator's hand-adds rather than by the
engine guessing taste.

### 1–15: Fresh Front

The songs Race added to the public playlist since the last run, newest first.
This tier *is* the curator's current vote. A song that is also in heavy rotation
is pulled into the top 5. At most two songs per artist, so an artist binge does
not swallow the front. When fewer than 15 were added in a week, the remaining
slots roll in the next-freshest songs.

### 16–100: Body

Everything else, ordered by add-recency with a light listening and popularity
nudge, and a small Hall-of-Fame penalty so brand-memory songs do not flood it.
The body holds a stable relative order week to week instead of reshuffling.
Hand-adds are protected from the weekly trim; the oldest tracks retire to keep
the list at 100.
```

Also update the "### 1-10: Premium Current Tier" guidance earlier in the doc if it remains — delete the line "The top 10 should not simply be the 10 newest songs." (it now is, by design).

- [ ] **Step 4: Commit**

```bash
git add data/dashboard/liveSpotify.ts README.md docs/cannabliss-philosophy.md
git commit -m "docs: describe the two-tier fresh-front model"
```

---

### Task 10: Full-suite green + final verification

**Files:** none (verification only).

- [ ] **Step 1: Run the entire test suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — all tests green, no references to removed helpers.

- [ ] **Step 2: Grep for leftovers**

Run: `rg -n "premium_current|high_conviction|stabilizers|front_queue|_score_track|MAJOR_TOP_10" src tests`
Expected: no matches.

- [ ] **Step 3: Dry-run sanity (manual, needs `.env`)**

Run: `DRY_RUN=1 python -m src.main`
Expected: prints the fresh-front preview, a cooldown line, and "🏜️ DRY RUN — no changes made to Spotify." with no traceback.

- [ ] **Step 4: Final commit (if any verification fixups were needed)**

```bash
git add -A
git commit -m "test: confirm fresh-front suite green end-to-end"
```

---

## Self-Review

**Spec coverage:**
- Top 15 = freshest hand-adds, newest first → Task 4/6 (`_build_fresh_front`, `test_weekly_adds_become_the_front_newest_first`). ✓
- Mid-week promotion (micro) → Task 6 (`test_micro_promotes_adds_and_preserves_everything`). ✓
- Added + heavily-played → top 5 → Task 4/6 (`test_hot_pick_*`). ✓
- 2-per-artist in the front → Task 4/6 (`test_artist_binge_capped_in_front_but_all_kept`). ✓
- Removed not re-added next week → Task 2/6/7 (cooldown helpers, `test_cooldown_excludes_*`, persistence). ✓
- Manual re-add overrides cooldown → Task 6 (`test_cooldown_overridden_by_manual_readd`). ✓
- Protection + trim oldest → Task 6 (`test_protected_adds_survive_trim_and_oldest_retire`). ✓
- One body score + stability → Task 3/5/6 (`_body_score`, `test_incumbents_hold_relative_order_on_score_ties`). ✓
- Hall penalty → Task 3/6 (`test_hall_track_sits_below_equivalent_non_hall_in_body`). ✓
- Two-tier zones → Task 6 (`test_zones_are_two_tiers_partitioning_the_playlist`). ✓
- Config knobs + workflows → Task 1/8. ✓
- Dashboard/README/philosophy → Task 9. ✓
- Listening-window caveat (short_term proxy) → no code; documented in spec. ✓ (no task needed)

**Placeholder scan:** No TBD/TODO; every code step shows complete code. ✓

**Type consistency:** `_build_fresh_front` / `_build_body` / `_front_sort_key` / `_body_sort_key` / `_is_hot_pick` / `active_cooldown_uris` / `merge_cooldown` / `previous_run_track_uris` / `append_cannabliss_run` signatures match across the tasks that define and consume them. `CannablissBuildResult.removed_uris` defined in Task 6, consumed in Task 7. `zones` keys (`fresh_front`/`body`) consistent across Tasks 6, 7, 9. ✓
