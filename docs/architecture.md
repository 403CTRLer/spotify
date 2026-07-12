# Architecture

## Module boundaries

```
cli/app.py ─────────────┐                    mcp/server.py
  (print/input live     │                      (FastMCP assembly, stdio,
   ONLY here; resolves  │                       tool annotations from the
   refs at the boundary)│                       capabilities registry)
                        ▼                          ▼
                 services/service.py  ◄──── tools/definitions.py
                  (all business logic;       (thin adapters; resolve refs at
                   explicit ids only;         the boundary via utils/links,
                   no I/O with humans)         dump models to dicts HERE)
                        │                          │
                        │                     tools/capabilities.py
                        │                (capability metadata: read_only,
                        │                 destructive, idempotent, confirm,
                        │                 scopes - single source of truth)
                        ▼
              repository/spotify.py
        SpotifyRepository (Protocol) ── typed contract: Page[T], PlayedItem,
        SpotifyApiRepository            models (models/schemas.py). Methods
          (atomic Web API operations     are atomic API operations only -
           only: one method = one         no workflow logic below this line.
           endpoint concern; pagination,
           chunking, null filtering)
                        │
                        ▼
                  api/client.py
          SpotifyApiClient (HTTP mechanics only:
          bearer auth, 401 refresh-retry, 429 backoff,
          pagination cursor following)
                        │
                        ▼
                 auth/oauth.py
          SpotifyAuth (PKCE flow, token cache,
          serialized refresh)

Leaves (no project-internal imports except each other):
  config/settings.py      env + .env resolution
  exceptions/errors.py    SpotifyMcpError family
  models/schemas.py       Playlist, Track, User + Page/PlayedItem
  utils/links.py          parse_ref/to_uri (pure parser, no semantics)
  utils/logging.py        stderr-only logging setup
```

## Rules that keep the layers honest

- **Only `cli/` prints or prompts.** stdout is the MCP wire protocol;
  everything else logs to stderr via `utils/logging.py`.
- **Repository methods are atomic Spotify API operations only.** One method
  maps to one endpoint concern (a call, or a call plus its pagination). There
  is no orchestration, sequencing, or algorithm below the service layer - for
  example `reorder_playlist` is a single `PUT` call; the shuffle *algorithm*
  (Fisher-Yates as a sequence of reorders) lives entirely in
  `SpotifyService.shuffle_playlist`.
- **Services are transport-agnostic.** Every method takes explicit, typed
  identifiers (`playlist_id: str`, `track_ids: Sequence[str]`,
  `(kind, spotify_id)` pairs) - never a URL or URI. Reference parsing and any
  policy about bare IDs happen exclusively in `cli/` and `tools/`, both via
  `utils.links.parse_ref`. This keeps services independently testable against
  a plain in-memory fake with no knowledge of Spotify's reference formats.
- **Services depend on the `SpotifyRepository` Protocol, never on HTTP.**
  Repository tests run against `httpx.MockTransport`; service tests run
  against an in-memory fake. A second provider implements the protocol from
  its method signatures alone (typed envelopes - see ADR 0003).
- **The API client knows HTTP, not endpoints.** Status handling, retries, and
  pagination live there; paths and payload shapes live in the repository.
- **The capability surface has one source of truth.**
  `tools/capabilities.py` declares, per tool, whether it is read-only,
  destructive, idempotent, requires confirmation, and which OAuth scopes it
  needs. `mcp/server.py` derives `ToolAnnotations` from it; a test asserts the
  registry and the requested OAuth scopes never drift apart.
- **Errors stay inside two families**: `SpotifyMcpError` subclasses
  (`AuthError`, `ApiError`, `NotFoundError`, `RateLimitError`) and
  `ValueError` for malformed input/data. The CLI maps both to exit 1; FastMCP
  maps them to `isError` tool results.

## Request flow (example: `add_to_playlist` MCP tool)

1. MCP client calls `add_to_playlist(playlist="https://open.spotify.com/playlist/…", tracks=["spotify:track:…"])`.
2. `tools/definitions.py` resolves both references to bare ids via
   `parse_ref` (the tool boundary) → calls
   `service.add_to_playlist(playlist_id, track_ids)` with explicit ids only.
3. `SpotifyService.add_to_playlist` formats ids as URIs and calls the
   repository - no reference parsing happens here.
4. `SpotifyApiRepository.add_items` chunks the URIs at Spotify's documented
   100-per-request limit and POSTs each chunk.
5. `SpotifyApiClient._request` injects the bearer token per call; on 401 it
   refreshes once (serialized, reuse-detecting - see `docs/security.md`); on
   429 it sleeps per `Retry-After` up to 3 times or fails fast past the 30s
   cap.
6. The tool returns a plain string/dict; FastMCP serializes the result.

## Shuffle: an in-place, lossless algorithm entirely in the service layer

`shuffle_playlist(playlist_id)` runs Fisher-Yates as a sequence of single-item
moves against the atomic `reorder_playlist` operation, threading the
playlist's `snapshot_id` (an optimistic-concurrency token, fetched once via
`playlist_snapshot_id` and never part of the `Playlist` domain model) from
call to call. No track is ever removed or re-added - every item, including
local files, survives by construction, and a mid-run failure just leaves the
playlist partially shuffled. This is the clearest illustration of the
repository/service split: the repository exposes one atomic move; the
algorithm that turns N moves into a full shuffle is business logic, and lives
only in the service.

## State on disk

`~/.spotify-mcp/tokens.json` (token cache) and `~/.spotify-mcp/tokens.lock`
(refresh lock) live in the home directory because MCP servers launch with an
arbitrary cwd; an optional `~/.spotify-mcp/.env` is a config fallback. There
is no other persistent state - the in-place shuffle algorithm has nothing to
snapshot or recover.

## Reserved extension namespaces

`analytics/`, `recommendations/`, `cache/`, `sync/`, `history/` are reserved
but intentionally NOT created: git cannot track empty directories and YAGNI
applies. A new provider (e.g. a future last.fm backend) implements a
`SpotifyRepository`-shaped protocol behind the same intent-named tools; none
of these belong in this repository, which stays exclusively a Spotify
connector (see [ADR 0006](adr/0006-scope-slimming-and-in-place-shuffle.md)).
