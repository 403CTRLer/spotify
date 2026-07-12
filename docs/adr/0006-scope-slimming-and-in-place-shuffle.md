# ADR 0006: Reusable Spotify-only connector - in-place shuffle, workflow slimming, explicit-id services

Date: 2026-07-12 · Status: accepted · Supersedes: ADR 0002 · Trigger: production-readiness reuse pass

## Context

The project was being positioned as a generic, open-source Spotify connector
for any MCP client, with an explicit non-goal of AI/curation/business logic.
Three structural issues stood in the way:

1. **Shuffle was destructive-by-necessity.** The snapshot/replace-PUT design
   (ADR 0002) removed and re-added every track, requiring a local-track guard
   and a whole recovery/restore subsystem to make it safe. That subsystem was
   pure incidental complexity around a workflow that Spotify's API can do
   losslessly.
2. **The repository leaked workflow logic.** `replace_items`,
   `all_playlist_uris` returning a `(uris, skipped)` tuple for a guard, and
   `album_track_uris` for a mix branch nobody asked to keep were all sequencing
   or policy decisions that belong above the repository.
3. **Services accepted URLs/URIs directly**, parsing references themselves.
   That makes the service layer depend on Spotify's reference formats and
   blurs the transport boundary the architecture is supposed to enforce.

## Decision

- **Shuffle is rewritten as an in-place reorder.** `SpotifyRepository` gains
  one atomic method, `reorder_playlist(playlist_id, range_start,
  insert_before, snapshot_id) -> str` (a single `PUT .../tracks` call). The
  service runs Fisher-Yates as a sequence of these calls, threading the
  playlist's `snapshot_id` - a transient optimistic-concurrency token
  (fetched via `playlist_snapshot_id`, never added to the `Playlist` domain
  model). No track is ever removed, so every item - including local files -
  survives by construction. `# TODO` marks a future similarity-based ordering
  as an explicit non-goal for now (pure random is correct and complete).
- **The snapshot/restore recovery system is removed entirely.** It existed
  only to make a destructive shuffle safe; an intrinsically lossless shuffle
  needs no recovery path. `shuffle-all` and `restore` are removed with it.
- **Mix is scoped to playlists and tracks.** Album sources are dropped (the
  album-tracks repository method had no other caller); mix stays strictly
  additive (no change from its prior ADR).
- **Services take explicit identifiers only.** Every `SpotifyService` method
  now takes `playlist_id: str`, `track_ids: Sequence[str]`, or
  `(kind, spotify_id)` pairs - never a ref string. `utils.links.parse_ref`
  is a pure parser (no `bare_type` inference); normalization policy for
  ambiguous bare IDs lives exclusively at the CLI and MCP boundaries, each
  calling `parse_ref` with the type its own parameter names.
- **The capability surface is described by data, not tool count.** See
  [ADR 0007](0007-capability-registry.md).

## Consequences

- `Playlist.total_tracks` becomes load-bearing for the shuffle loop bound
  (already present; no model change).
- Shuffling N tracks costs ~N API calls - slower than a bulk replace on large
  playlists under development-mode rate limits, but lossless and needs no
  safety net. Documented in the user guide and tool reference.
- Breaking for any external caller: `SpotifyRepository.replace_items`,
  `.album_track_uris`, and the `(uris, skipped)` return of
  `.all_playlist_uris` are gone; `SpotifyService` methods that used to accept
  a ref string now require explicit ids (acceptable pre-1.0).
