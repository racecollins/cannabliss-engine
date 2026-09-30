# Deployment and recovery

The approved first 100-song edition was activated and read back on September 30,
2026. A guarded live micro run then verified zero membership or order changes.
One post-preview nomination, Lose Yourself to Dance, was preserved in the queue.

## Scheduled configuration

- Friday 11:00 UTC: major refresh.
- Monday and Wednesday 15:00 UTC: nomination/preference capture and vacancy repair.
- Both workflows share `cannabliss-playlist` concurrency, cancellation disabled.
- Each runs tests, restores the public `cannabliss-state` branch to
  `data/runtime/cannabliss_state.json`, checkpoints before writing Spotify and
  verifies the resulting order before saving successful history.
- Default weekly intake 15; weekly ceiling 20 including up to 10 queued curator
  picks. Nominations become eligible the following UTC calendar week. Admission
  starts their 14-day protection. Automatic retirement cooldown is 42 days.
- Listening ranks, bounded reorder preferences and featured-week limits enabled.
- Master and archive are readable candidates. Spotify-owned discovery playlists
  are not connected. The archive is read once, not duplicated as a feeder.
- Manual dispatch defaults to dry-run. `CANNABLISS_EXPECT_NOOP=1` additionally
  rejects any live plan that would change the playlist during activation checks.
- Workflow `contents: write` permission publishes only the dedicated state branch
  in normal operation. User explicitly approved public song/order/queue metadata.
  Credentials stay in Actions secrets. Preview/recovery artifacts last 30 days.

## Recovery

An unresolved local `.pending.json` or remote `pending_update.json` stops future
runs. Never clear it merely to get the scheduler running. Compare its `before`
and `after` URI orders to a fresh Spotify read:

- If Spotify matches `before`, archive the checkpoint and rerun a fresh preview
  after clearing the reconciled pending transaction.
- If Spotify matches `after`, recover the corresponding verified history,
  including the checkpoint's `proposed_rotation` queue/preference metadata,
  before clearing it. Do not fabricate a different successful run.
- If neither matches, preserve the current playlist and reconcile manually.

Queue metadata is checkpointed before overflow nominations leave Spotify.
Only a matched readback advances verified state. A non-fast-forward history push
fails instead of overwriting another writer. Avoid editing while a live run is
writing; Spotify replacement has no atomic compare-and-swap in this client.

`src.activate_edition` is a one-time, explicitly reviewed migration utility. It
refuses to replace an existing history branch or reuse an existing activation
state. Normal weekly runs must never use it to reset learning.
