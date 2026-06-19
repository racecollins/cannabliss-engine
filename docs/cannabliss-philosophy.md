# Cannabliss Scoring Philosophy

## Summary

Cannabliss is a discovery + vibe playlist built around stoner hip-hop, psychedelic or alternative rap, and chill rap discovery. It should feel current and alive without becoming a pure release-radar playlist. The goal is not to chase every new song. The goal is to present the best version of the Cannabliss point of view each week.

This document is meant to serve two audiences at once:

- a human curator making taste decisions by hand
- an engineer translating those taste decisions into automation logic later

It is intentionally editorial first and technical second.

## Cannabliss Identity

Cannabliss should feel:

- hazy
- melodic
- trippy
- replayable
- current but tasteful

Cannabliss should not feel like:

- a generic new music roundup
- a chart playlist with a few underground songs mixed in
- a random collection of favorites with no sequencing logic

The playlist should reward discovery, but the listening experience should still feel smooth, authored, and easy to stay inside for 30 minutes or more.

## Playlist Roles

### Cannabliss Public Playlist

This is the listener-facing product. It should sit around `160-180` songs and update weekly. It is the playlist that followers experience as the Cannabliss brand.

### Cannabliss Master

This is the large source pool. It contains:

- many candidate songs
- feeder playlist pulls
- recently added curator picks
- songs waiting to prove they belong in the public playlist

Master is a source of discovery, not a finished listening experience.

### Cannabliss Hall of Fame

This is the archive of songs that were previously important to Cannabliss. Hall of Fame songs are not part of the normal weekly intake, but they can occasionally return if they strongly fit the current moment.

Hall of Fame should act as brand memory, not as a primary weekly content source.

### Feeder Playlists

Feeder playlists are external or adjacent sources that help surface songs that fit the Cannabliss lane. For v1, the default feeder set is:

- Lorem
- Anti-Pop
- Cannabliss Hall of Fame

The feeder list should remain configurable.

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

## How Songs Earn Placement

### Promote

A song should be promoted upward when it:

- feels especially current inside the Cannabliss lane
- keeps earning replay value
- works as an anchor or standout moment in sequence
- makes the front of the playlist feel stronger rather than merely newer

Promotion is not just about novelty. It is about fit, strength, and timing.

### Hold

A song should hold its position when it:

- still feels strong in its current zone
- continues to support the playlist flow
- does not demand promotion but also does not feel stale

Holding is success. Not every good song needs to climb.

### Shift Down

A song should shift downward when it:

- is still on-brand but no longer feels front-half urgent
- has already had a strong run near the top
- works better as a supporting or stabilizing song than as a headline record

Shifting down is part of normal playlist life, not a failure.

### Retire

A song should be removed when it:

- no longer feels essential to the current Cannabliss shape
- weakens the pacing or identity of the playlist
- has fallen past the bottom of the target size after repeated downward shifts

Retired songs do not need to be bad songs. They may simply no longer be the right fit for the current moment.

### Hall of Fame Return

A Hall of Fame song may return when it:

- still feels deeply canonical to Cannabliss
- fits the current emotional lane
- adds meaning, memory, or familiarity without making the playlist feel stale

Hall of Fame returns should be occasional and intentional.

## Treatment of New Songs vs Older Rediscoveries

Cannabliss is a hybrid of discovery and curator taste. Because of that, the system should prioritize songs that were recently added to the Cannabliss system, not only songs that were recently released.

That means:

- older songs you are newly excited about are fully valid Cannabliss candidates
- a rediscovered song from 10 years ago can still earn a top-tier slot
- newly released songs should get a light edge when two songs are otherwise similarly strong

Release recency should be a soft bias, not a hard gate.

## Proven Glue and Sequencing

Proven glue songs should be sprinkled throughout the playlist rather than pushed into one low block.

This matters because:

- listeners engage the top half most heavily
- the playlist should feel stable and authored, not segmented into “all risky songs first, all safe songs later”
- anchor songs make discovery feel easier to trust

Glue songs should be used as stabilizers between fresher or riskier tracks, especially in the first `50-80` songs.

## Anti-Patterns

These songs may be individually good but should usually be filtered out of top placement or excluded entirely:

- songs that break the Cannabliss spell even if they are objectively strong
- songs that feel too mainstream-chart-driven for the playlist identity
- songs that are too sleepy to support the front 50
- songs that are too noisy, abrasive, or chaotic for the vibe lane
- songs that feel technically similar to the playlist but emotionally off-brand

The key question is not “is this good?” It is “does this make Cannabliss better?”

## Automation Bridge

The editorial rules above should map to future automation signals.

### Editorial Principle: Current but tasteful

Possible automation signals:

- system-add recency
- light release-recency bias
- recent presence in feeder playlists

### Editorial Principle: Discovery with identity

Possible automation signals:

- source playlist membership
- prior Cannabliss incumbency
- Hall of Fame membership or prior Hall of Fame promotion
- artist repetition controls

### Editorial Principle: Front-half quality bar

Possible automation signals:

- stronger promotion thresholds for positions `1-25`
- higher fit requirements for premium current songs
- persistence rules that allow strong incumbents to stay near the top

### Editorial Principle: Smooth flow

Possible automation signals:

- optional cohesion or sequencing compatibility
- pacing-aware insertion of glue songs
- optional audio-feature checks used lightly, not mechanically

### Editorial Principle: Small market awareness without selling out

Possible automation signals:

- Spotify popularity used as a weak tie-breaker
- no hard popularity cutoffs
- popularity never overrides fit or brand identity

## V1 Scoring Direction

For the first Cannabliss automation version, the scoring hierarchy should be:

### Primary signals

- addition recency within the Cannabliss system
- source bucket membership
- Cannabliss incumbency and prior performance
- front-half placement rules

### Secondary signals

- release recency as a light bias
- Hall of Fame return eligibility
- glue or anchor suitability

### Tie-breakers

- Spotify popularity
- optional cohesion or sequencing compatibility

Hard numeric weights are not required yet. The first goal is to preserve the Cannabliss point of view clearly enough that scoring logic can be added without re-deciding what the playlist is.
