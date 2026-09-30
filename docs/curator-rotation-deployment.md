# Deployment and recovery — pending review

The engine changes are local on `fix/curator-first-rotation`. No scheduled
workflow, GitHub secret, or Spotify playlist has been changed by this repair.

## Before live activation

1. Reconnect the existing Spotify app and replace its expired/revoked refresh
   token. Use the existing authorization helper locally with the app credentials
   supplied securely; do not paste tokens into chat or commit them.
2. Run a dry preview against the live Master and public playlist. Inspect the
   full Markdown/JSON report and the first-baseline warning.
3. After approval, wire both scheduled workflows to the tested durable history
   module. These changes are deliberately not applied yet.

## Concrete workflow changes awaiting approval

Both workflows need the following changes together:

- One shared concurrency group, `cannabliss-playlist`, with cancellation disabled
  so weekly and midweek jobs never plan or write at the same time.
- A test step before every run (`python -m pytest tests/ -q`).
- Restore history before planning: `python -m src.state_store restore`.
- `CANNABLISS_GIT_STATE=1` for the engine. Live writes then checkpoint a pending
  transaction before Spotify changes and commit verified history afterward.
- Repository `contents: write` permission for that isolated state branch.
- Keep the state file path `data/cannabliss_state.json`, use protection 14 days,
  discovery-per-refresh 15, weekly insertions 20, removal cooldown 42 days,
  ranked top tracks enabled and `CANNABLISS_LEARN_TOP_TEN=1`. Reconcile existing
  environment overrides; changing defaults alone does not change deployed settings.
- Generate a complete preview with
  `CANNABLISS_PREVIEW_PATH=data/preview/cannabliss.md`.
- Keep dispatch defaults at `DRY_RUN=1`; scheduled live writes should remain
  gated off until preview approval and explicit activation.
- If approved, retain preview, verified-state, and pending-plan recovery files
  as workflow artifacts for 30 days. These contain playlist metadata, not tokens.
  Artifact visibility follows repository access, so this is a publication step.

The isolated branch is named `cannabliss-state` and contains only
`cannabliss_state.json` and, while a transaction is pending, `pending_update.json`.
The source branch is never used as a state database. The dashboard still reads
its local committed JSON; connecting it to this branch is outside this repair.

## Interrupted update recovery

A `.pending.json` local file or a remote `pending_update.json` means the last
write could have reached Spotify without a verified durable completion. The
engine stops; it does not assume the write failed or repeat it automatically.

Compare the saved `before` and `after` URI orders to a fresh Spotify read:

- If Spotify matches `before`, no final playlist change occurred. Preserve an
  audit copy, then clear the pending checkpoint and rerun a preview.
- If Spotify matches `after`, restore the corresponding verified run state from
  the saved run artifact if available. If it is not available, explicitly
  establish a new reviewed baseline; do not fabricate successful history.
- If Spotify matches neither, preserve the current playlist and reconcile the
  differences manually before clearing the checkpoint.

Do not clear a pending checkpoint merely to make the next run proceed. A
non-fast-forward state push also stops the run instead of overwriting another
writer's history. The small race between the final preflight read and Spotify's
replace request cannot be eliminated by this API usage; avoid editing the
playlist during a live run. A post-write mismatch stops history advancement.

## September 30 preference-learning update

Local code now learns relative top-ten reorder preferences only against the last
verified output. No live order has been imported as a fabricated successful run.
The reviewed first edition is still an editorial proposal, not an applied
baseline. Enable the settings above only with the reviewed migration and durable
history wiring. The first successful readback establishes `rotation.verified_order`;
subsequent user edits are observed at the next refresh. A dry preview computes but
does not persist learning. Do not interpret other collaborators' edits as proof
of this user's intent; the API order comparison does not identify an editor.

## Queued nominations

Enable `CANNABLISS_QUEUE_CURATOR_ADDITIONS=1` and set
`CANNABLISS_CURATOR_QUEUE_PER_REFRESH=10`. Pending transaction checkpoints now
include `proposed_rotation`, containing the complete queued track metadata
before overflow can leave Spotify. Verified success publishes the proposed queue
with rotation history; failures leave the previous state and recovery checkpoint
intact. Recovery must reconcile both playlist order and that queue, not discard
pending data. Queue entries are shown in preview JSON and Markdown.
