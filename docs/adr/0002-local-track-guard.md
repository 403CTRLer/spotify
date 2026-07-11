# ADR 0002: Shuffle refuses playlists containing local/unavailable tracks

Date: 2026-07-11 · Status: accepted · Trigger: review finding #1

## Context

The repository filters out local and null (catalog-removed) tracks because the
Web API cannot re-add them. Combined with shuffle's replace-PUT, this silently
rewrote playlists WITHOUT those tracks - permanent loss that the recovery
snapshot (built from the same filtered list) could not restore. The API offers
no way to preserve them through a rewrite, so this cannot be "fixed", only
guarded.

## Decision

- `all_playlist_uris` returns `(streamable_uris, skipped)` so destructive
  callers see what a rewrite would drop.
- `shuffle_playlist` raises `LocalTracksError` when `skipped` is non-empty,
  unless `force=True`; snapshots record the skipped entries either way.
- `shuffle-all` skips such playlists (reported, untouched) rather than
  aborting the whole run or forcing.
- Additive operations (mix, collect) keep filtering silently - adding to
  another playlist destroys nothing in the source.

## Consequences

- Behavior change: previously "successful" shuffles of such playlists now
  refuse by default. `--force` restores the old outcome, explicitly.
- The protocol method's return type changed (breaking for implementers;
  acceptable pre-1.0, both implementations updated in the same commit).
