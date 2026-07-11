# ADR 0001: Mix is additive-only

Date: 2026-07-11 · Status: accepted · Trigger: review finding #2

## Context

`mix_playlists` preserved legacy semantics: remove the mixed tracks from the
target, then re-add them shuffled. A failure between the two calls (rate limit
exhaustion, network drop) permanently stripped every overlapping track from
the target, with no snapshot - the exact data-loss class the shuffle fix had
just closed.

## Options

1. Keep remove-then-add, snapshot the target first (mirrors shuffle).
2. Make mix additive: fetch target contents, append only what's missing,
   never remove.

## Decision

Option 2. A snapshot narrows the window but keeps a destructive step that the
operation doesn't actually need; restore-by-replace after a failed mix would
also drop local tracks that survived the mix. Additive mix removes the
failure mode instead of guarding it - the worst mid-flight outcome is a
partial append, which re-running completes.

## Consequences

- Behavior change: tracks already in the target keep their position instead
  of moving to the end; the duplicate count now includes overlap with the
  target. Documented in the user guide and CHANGELOG (0.2.0).
- One extra read (target contents) per mix; no destructive calls at all.
