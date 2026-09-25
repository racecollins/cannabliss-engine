"""Durable GitHub Actions history on an isolated branch.

Both refresh workflows use one concurrency group. A pending checkpoint is pushed
BEFORE Spotify is changed; an interrupted write or failed final push therefore
blocks subsequent runs until the operator reconciles Spotify and saved history.
No secrets are stored here, only playlist metadata and the expected URI orders.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess

from src.cannabliss import load_cannabliss_state, save_cannabliss_state

BRANCH = "cannabliss-state"
STATE_FILE = "cannabliss_state.json"


def git(*args, input=None, check=True):
    return subprocess.run(["git", *args], input=input, text=True,
                          capture_output=True, check=check)


def remote_head():
    result = git("ls-remote", "--exit-code", "--heads", "origin", f"refs/heads/{BRANCH}", check=False)
    if result.returncode == 2:
        return None
    if result.returncode:
        raise RuntimeError("Cannot read durable history from origin; refusing to reset state")
    git("fetch", "--no-tags", "origin", f"refs/heads/{BRANCH}")
    return git("rev-parse", "FETCH_HEAD").stdout.strip()


def restore(path):
    head = remote_head()
    if head is None:
        print("No durable history branch yet; first live run will establish the baseline.")
        return
    files = git("ls-tree", "--name-only", head).stdout.splitlines()
    if "pending_update.json" in files:
        raise RuntimeError(
            "An earlier Spotify update has an unresolved pending checkpoint on cannabliss-state. "
            "Compare its before/after orders with Spotify and recover the matching run artifact "
            "before continuing. No automatic retry is safe."
        )
    payload = json.loads(git("show", f"{head}:{STATE_FILE}").stdout)
    if payload.get("schema_version") != 2 or not isinstance(payload.get("rotation"), dict):
        raise ValueError("Durable history is not valid version 2 state")
    save_cannabliss_state(payload, path)
    print("Restored verified history from cannabliss-state.")


def checkpoint(path, *, pending=None):
    parent = remote_head()
    if pending is not None and parent is not None:
        if "pending_update.json" in git("ls-tree", "--name-only", parent).stdout.splitlines():
            raise RuntimeError("Refusing to overwrite an unresolved pending checkpoint")
    payload = load_cannabliss_state(path)
    files = {STATE_FILE: json.dumps(payload, indent=2) + "\n"}
    if pending is not None:
        files["pending_update.json"] = json.dumps(pending, indent=2) + "\n"
    entries = []
    for name, content in sorted(files.items()):
        blob = git("hash-object", "-w", "--stdin", input=content).stdout.strip()
        entries.append(f"100644 blob {blob}\t{name}\n")
    tree = git("mktree", input="".join(entries)).stdout.strip()
    args = ["-c", "user.name=Cannabliss automation", "-c",
            "user.email=41898282+github-actions[bot]@users.noreply.github.com", "commit-tree", tree]
    if parent:
        args += ["-p", parent]
    message = "Checkpoint pending playlist update" if pending is not None else "Save verified playlist history"
    commit = git(*args, input=message + "\n").stdout.strip()
    # Non-force push refuses a concurrent writer instead of losing its history.
    git("push", "origin", f"{commit}:refs/heads/{BRANCH}")
    print(message + " on cannabliss-state.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["restore"])
    parser.add_argument("--path", default=os.environ.get("CANNABLISS_STATE_PATH", "data/cannabliss_state.json"))
    args = parser.parse_args()
    restore(args.path)


if __name__ == "__main__":
    main()
