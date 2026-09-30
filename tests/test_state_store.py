"""Exercise durable state against a real local Git remote, without Spotify."""

import json
import subprocess

import pytest

from src.cannabliss import load_cannabliss_state
from src.state_store import checkpoint, restore


def test_state_roundtrip_and_interrupted_write_blocks_next_run(tmp_path, monkeypatch):
    remote = tmp_path / "remote.git"
    local = tmp_path / "local"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "clone", str(remote), str(local)], check=True, capture_output=True)
    monkeypatch.chdir(local)
    path = local / "history.json"
    restore(str(path))
    assert not path.exists()
    payload = {"schema_version": 2, "runs": [], "rotation": {"version": 2, "tracks": {}}}
    path.write_text(json.dumps(payload))
    checkpoint(str(path))
    restored = local / "restored.json"
    restore(str(restored))
    assert load_cannabliss_state(str(restored)) == payload
    checkpoint(str(path), pending={"before": ["old"], "after": ["new"]})
    with pytest.raises(RuntimeError, match="pending checkpoint"):
        restore(str(restored))
    checkpoint(str(path))
    restore(str(restored))
    assert load_cannabliss_state(str(restored)) == payload


def test_corrupt_local_history_is_not_silently_replaced(tmp_path):
    path = tmp_path / "history.json"
    path.write_text("broken")
    with pytest.raises(ValueError):
        load_cannabliss_state(str(path))
    assert path.read_text() == "broken"
