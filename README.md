# spotify-mcp

Lightweight Spotify Web API foundation: a typed service layer, a developer CLI,
and an MCP server exposing 10 provider-agnostic music tools.

The original script-based project lives on the [`legacy`](../../tree/legacy) branch.

## Setup

1. Create an app on the [Spotify developer dashboard](https://developer.spotify.com/dashboard).
   Register the redirect URI **exactly** as `http://127.0.0.1:8888/callback`
   (Spotify rejects `http://localhost` for apps created after April 2025).
   The PKCE flow needs **no client secret**.
2. Copy `.env.example` to `.env` and set `SPOTIFY_CLIENT_ID`. The file is read
   from the working directory, falling back to `~/.spotify-mcp/.env` (useful
   when an MCP client launches the server with an arbitrary cwd).
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
`remove_from_playlist`, `library_tracks`, `recent_history` - full schemas,
shapes, and error behavior in [docs/tool-reference.md](docs/tool-reference.md).
References may be Spotify URLs, `spotify:` URIs, or bare IDs.

## CLI

```sh
uv run spotify-mcp playlists
uv run spotify-mcp mix SOURCE [SOURCE ...] --into TARGET   # additive: never removes
uv run spotify-mcp shuffle PLAYLIST [--force]
uv run spotify-mcp shuffle-all --ignore "chill,https://open.spotify.com/playlist/..."
uv run spotify-mcp restore SNAPSHOT.json                   # recover a failed rewrite
uv run spotify-mcp liked-to-playlist TARGET
uv run spotify-mcp clear-liked        # destructive; asks for confirmation
```

Safety model for destructive operations:

- `shuffle` writes a full-track-list snapshot to `~/.spotify-mcp/recovery/`
  **before** touching the playlist and deletes it on success; a failed run
  names the snapshot, and `restore` applies it.
- Playlists containing **local/unavailable tracks** refuse to shuffle (a
  rewrite would drop them permanently); `--force` overrides, recording the
  dropped entries in the snapshot. `shuffle-all` skips such playlists.
- `mix` is additive-only: it never removes tracks, so there is no
  partial-failure data-loss window.

Details and failure modes: [docs/recovery.md](docs/recovery.md) ·
Command walkthroughs: [docs/user-guide.md](docs/user-guide.md)

## Documentation

| Doc | Contents |
|---|---|
| [docs/user-guide.md](docs/user-guide.md) | every CLI command with examples, exit codes |
| [docs/tool-reference.md](docs/tool-reference.md) | MCP tool schemas, shapes, errors |
| [docs/architecture.md](docs/architecture.md) | module boundaries, request flow |
| [docs/recovery.md](docs/recovery.md) | snapshots, restore, failure modes |
| [docs/security.md](docs/security.md) | OAuth/PKCE, token storage, refresh, limitations |
| [docs/development.md](docs/development.md) | structure, testing, CI, releases |
| [docs/adr/](docs/adr/) | architecture decision records |

## Development

```sh
uv sync
uv run pre-commit install
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
```

CI runs the same gate (with `uv sync --frozen`) plus a gitleaks secret scan on
every push/PR to `main`. Branch workflow: branch from `main`, PR back into
`main`; `legacy` is frozen. Releases follow SemVer with notes in
[CHANGELOG.md](CHANGELOG.md).

## Architecture (short version)

```
cli/  mcp/ -> tools/ -> services/ -> repository/ (Protocol) -> client/ -> auth/
                          models/, utils/, exceptions/, config/ are leaves
```

Key decisions (full rationale in [docs/architecture.md](docs/architecture.md)
and the ADRs): PKCE with no client secret; sync httpx; snapshot-before-replace
shuffle with a local-tracks guard; additive mix; typed repository envelopes
(`Page[T]`); home-dir state; 8 OAuth scopes; pydantic for Playlist/Track/User
only; reserved extension namespaces (`analytics/`, `recommendations/`,
`cache/`, `sync/`, `history/`) created only when they gain a consumer.

### Note on history

Commit history before the rewrite contains a Spotify client credential pair.
It has been rotated and is dead; the `legacy` branch preserves that history
intentionally. See [docs/security.md](docs/security.md).
