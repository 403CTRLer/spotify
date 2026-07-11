# Architecture

## Module boundaries

```
cli/app.py ─────────────┐                    mcp/server.py
  (print/input live     │                      (FastMCP assembly, stdio)
   ONLY here)           │                          │
                        ▼                          ▼
                 services/service.py  ◄──── tools/definitions.py
                  (all business logic;       (10 thin adapters; models are
                   no I/O with humans)        dumped to dicts HERE and only here)
                        │
                        ▼
              repository/spotify.py
        SpotifyRepository (Protocol) ── typed contract: Page[T], NowPlaying,
        SpotifyApiRepository            PlayedItem, models (models/schemas.py)
          (endpoints, pagination assembly,
           chunking, null/local filtering)
                        │
                        ▼
              client/api_client.py
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
  models/schemas.py       Playlist, Track, User + Page/NowPlaying/PlayedItem
  utils/links.py          parse_ref/to_uri
  utils/logging.py        stderr-only logging setup
```

Rules that keep the layers honest:

- **Only `cli/` prints or prompts.** stdout is the MCP wire protocol; everything
  else logs to stderr via `utils/logging.py`.
- **Services depend on the `SpotifyRepository` Protocol, never on HTTP.**
  Service tests run against an in-memory fake; repository tests run against
  `httpx.MockTransport`. A second provider implements the protocol from its
  signatures alone (typed envelopes, review #7).
- **The client knows HTTP, not endpoints.** Status handling, retries, and
  pagination live there; paths and payload shapes live in the repository.
- **Errors stay inside two families**: `SpotifyMcpError` subclasses
  (`AuthError`, `ApiError`, `NotFoundError`, `RateLimitError`,
  `LocalTracksError`) and `ValueError` for malformed input/data. The CLI maps
  both to exit 1; FastMCP maps them to `isError` tool results.

## Request flow (example: `playlist_items` MCP tool)

1. MCP client calls `playlist_items(playlist="https://open.spotify.com/playlist/…", limit=100)`.
2. `tools/definitions.py` → `get_service()` (cached singleton wired from
   `Settings.from_env()`).
3. `services.playlist_items` parses the reference via `utils/links.parse_ref`
   (URL/URI/bare-ID, type asserted) → repository call with the bare ID.
4. `repository.playlist_items` clamps `limit` to the endpoint max, GETs
   `/playlists/{id}/tracks`, filters null tracks, maps to `Track` models,
   returns `Page[Track]`.
5. `client._request` injects the bearer token per call; on 401 it refreshes
   once (serialized, reuse-detecting - see `docs/security.md`); on 429 it
   sleeps per Retry-After up to 3 times or fails fast past the 30s cap.
6. The tool dumps models to plain dicts; FastMCP serializes the result.

## State on disk

Everything lives in `~/.spotify-mcp/` because MCP servers launch with an
arbitrary cwd: `tokens.json` (token cache), `recovery/*.json` (shuffle
snapshots), optional `.env` (config fallback).

## Reserved extension namespaces

`analytics/`, `recommendations/`, `cache/`, `sync/`, `history/` are reserved
but intentionally NOT created: git cannot track empty directories and YAGNI
applies. A new provider (e.g. a future lastfm backend) implements a
`SpotifyRepository`-shaped protocol behind the same intent-named tools.
