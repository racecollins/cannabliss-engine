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
