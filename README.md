# spotify-mcp

Lightweight Spotify Web API foundation: a typed service layer, a developer CLI,
and an MCP server exposing 10 provider-agnostic music tools.

The original script-based project lives on the [`legacy`](../../tree/legacy) branch.

## Setup

1. Create an app on the [Spotify developer dashboard](https://developer.spotify.com/dashboard).
   Register the redirect URI **exactly** as `http://127.0.0.1:8888/callback`
   (Spotify rejects `http://localhost` for apps created after April 2025).
   The PKCE flow needs **no client secret**.
2. Copy `.env.example` to `.env` and set `SPOTIFY_CLIENT_ID`.
3. Install and log in:

```sh
uv sync
uv run spotify-mcp auth
```

Tokens are cached in `~/.spotify-mcp/tokens.json` and refreshed automatically.

## MCP server

```sh
uv run spotify-mcp serve   # stdio transport
```

Client config:

```json
{
  "mcpServers": {
    "spotify": { "command": "uv", "args": ["run", "spotify-mcp", "serve"], "cwd": "<this repo>" }
  }
}
```

Tools (intent-named, provider-agnostic): `user_profile`, `currently_playing`,
`playlists`, `playlist_items`, `search`, `create_playlist`, `add_to_playlist`,
`remove_from_playlist`, `library_tracks`, `recent_history`.
References may be Spotify URLs, `spotify:` URIs, or bare IDs.

## CLI

```sh
uv run spotify-mcp playlists
uv run spotify-mcp mix SOURCE [SOURCE ...] --into TARGET
uv run spotify-mcp shuffle PLAYLIST
uv run spotify-mcp shuffle-all --ignore "chill,https://open.spotify.com/playlist/..."
uv run spotify-mcp liked-to-playlist TARGET
uv run spotify-mcp clear-liked        # destructive; asks for confirmation
```

`shuffle` writes a full-track-list snapshot to `~/.spotify-mcp/recovery/`
before touching the playlist; on a mid-write failure the error message names
the snapshot file so nothing is ever lost.

## Development

```sh
uv sync
uv run pre-commit install
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
```

CI runs the same gate plus a gitleaks secret scan on every push/PR to `main`.
Branch workflow: branch from `main`, PR back into `main`; `legacy` is frozen.
Releases follow SemVer with notes in [CHANGELOG.md](CHANGELOG.md).

## Architecture

```
cli/  mcp/ -> tools/ -> services/ -> repository/ (Protocol) -> client/ -> auth/
                          models/, utils/, exceptions/, config/ are leaves
```

- **auth/** - OAuth Authorization Code + PKCE, rotating refresh tokens, atomic token cache.
- **client/** - `SpotifyApiClient`: HTTP mechanics only (bearer auth, 401 refresh-retry,
  429 Retry-After backoff, pagination). No endpoint knowledge.
- **repository/** - `SpotifyRepository` protocol + Web API implementation: endpoints,
  chunking (100 playlist / 50 library), null- and local-track filtering, model mapping.
- **services/** - all business logic against the protocol; never prints or prompts.
- **tools/ + mcp/** - thin MCP adapters and FastMCP assembly.
- **cli/** - the only layer that prints or prompts.

### Design decisions

- **PKCE, no secret**: nothing worth stealing in `.env`; the browser flow lives only in
  the `auth` command - the MCP server raises an actionable error instead of popping a browser.
- **Sync httpx**: FastMCP runs sync tools on worker threads; async would double the surface.
- **Snapshot-before-replace shuffle**: replace-PUT (first 100) + append avoids the legacy
  remove-then-add empty-playlist window; the snapshot is belt-and-braces on top.
- **Home-dir state** (`~/.spotify-mcp/`): MCP servers launch with an arbitrary cwd.
- **8 OAuth scopes** instead of the legacy 19: only what the tools use.
- **Pydantic for Playlist/Track/User only**: they feed FastMCP output schemas; everything
  else stays dicts until a consumer needs more.
- **`/me/playlists`** replaces the legacy `/users/{id}/playlists` for correct
  private-playlist visibility.
- **`mcp` subpackage** does not shadow the SDK: absolute imports + src layout.
- **Reserved extension namespaces** (added as packages when they gain a consumer, since
  git cannot track empty dirs): `analytics/`, `recommendations/`, `cache/`, `sync/`,
  `history/`. New providers implement `SpotifyRepository`-shaped protocols behind
  the same intent-named tools.

### Note on history

Commit history before the rewrite contains a Spotify client credential pair.
It has been rotated and is dead; the `legacy` branch preserves that history intentionally.
