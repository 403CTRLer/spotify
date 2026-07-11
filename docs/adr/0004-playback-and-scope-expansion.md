# ADR 0004: Playback control, personalization, and the scope expansion

Date: 2026-07-12 · Status: accepted · Trigger: production-readiness API audit

## Context

The 0.1-0.2 surface was playlist/library-centric. The API audit
([api-coverage.md](../api-coverage.md)) showed the highest-value uncovered
area was the Player API - "play this", "what's playing", "queue that" are the
most natural MCP interactions for a music server - plus Top Items and catalog
lookup. Meanwhile Spotify's Nov 2024 restrictions rule out the classic
discovery endpoints (recommendations, audio features, related artists) for
this app class entirely.

## Decision

- Implement the player core (state+devices, play/pause/skip/queue/volume),
  top items, single-item catalog lookup, library save, playlist
  update/unfollow. Skip player minutiae (seek, repeat, shuffle-mode,
  transfer-without-play, queue read) and social-graph endpoints until a
  consumer exists - each is a one-method addition.
- Requested scopes grow from 8 to 11 (`user-read-playback-state`,
  `user-modify-playback-state`, `user-top-read`). The existing scope-subset
  check turns this into a forced, actionable re-auth for existing users
  rather than runtime 403s.
- Restricted endpoints are documented as unimplementable (🚫) rather than
  attempted: they would 403 for every user of this app.
- Playback state and device dicts join `search` as documented
  `dict[str, Any]` exceptions to the typed-envelope rule (heterogeneous,
  dumped at source; ADR 0003 rationale applies).

## Consequences

- One scope grant now covers a mixed CLI/MCP usage profile; users who never
  use playback still grant playback scopes (acceptable for a personal tool,
  noted in the security guide).
- Playback control returns 403 for non-Premium accounts - surfaced as the
  API's own error message, documented everywhere the tools are.
