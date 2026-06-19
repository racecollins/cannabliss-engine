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


def test_invalid_max_per_artist_exits(monkeypatch):
    _set_env(monkeypatch, CANNABLISS_FRESH_FRONT_MAX_PER_ARTIST="0")
    with pytest.raises(SystemExit):
        validate_config(load_config())
