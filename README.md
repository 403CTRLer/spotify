# spotify-mcp

A reusable Spotify connector: an MCP server and a CLI over the Spotify Web
API. Exposes Spotify capabilities only - no AI, recommendation, curation, or
application-specific logic - so any MCP-compatible client (Claude, Cursor,
VS Code/Cline/Roo, OpenHands, ...) or shell script can drive Spotify through
the same service layer.

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

Connecting Claude Desktop/Code, Cursor, VS Code, Cline, Roo Code, OpenHands,
or any other stdio MCP client: [docs/clients.md](docs/clients.md).

Tools cover **Authentication** (handled outside MCP via `spotify-mcp auth`),
**User Profile**, **Search**, **Library** (saved tracks, top items, recent
history), **Playlists** (read/create/update/delete/add/remove/shuffle), and
**Playback** (state, play/pause/skip/queue/volume - Spotify Premium
required). Destructive tools use a two-step confirm protocol: the first call
returns a preview and makes no changes. Every tool's read-only/destructive/
idempotent behavior and required OAuth scope come from one place,
[`tools/capabilities.py`](src/spotify_mcp/tools/capabilities.py). Full
schemas: [docs/tool-reference.md](docs/tool-reference.md).

## CLI

`--json` gives machine-readable output on reads. By capability:

```sh
# Search & lookup
uv run spotify-mcp search "bicep glue" --type album
uv run spotify-mcp lookup <any spotify link>

# Library
uv run spotify-mcp like TRACK... / unlike TRACK...
uv run spotify-mcp recent / top tracks --range short

# Playlists
uv run spotify-mcp playlists / tracks PLAYLIST
uv run spotify-mcp create-playlist NAME / update-playlist / delete-playlist
uv run spotify-mcp mix SOURCE... --into TARGET   # additive: never removes
uv run spotify-mcp shuffle PLAYLIST              # in-place reorder: lossless
uv run spotify-mcp liked-to-playlist TARGET
uv run spotify-mcp clear-liked                   # destructive; asks for confirmation

# Playback (Spotify Premium)
uv run spotify-mcp now
uv run spotify-mcp play <link> / pause / next / prev / queue TRACK / volume N
```

Full walkthroughs: [docs/user-guide.md](docs/user-guide.md).

## Documentation

| Doc | Contents |
|---|---|
| [docs/user-guide.md](docs/user-guide.md) | CLI reference by capability, with examples |
| [docs/tool-reference.md](docs/tool-reference.md) | MCP tools by capability: schemas, confirm protocol, errors |
| [docs/api-coverage.md](docs/api-coverage.md) | full Spotify Web API coverage matrix with omission rationale |
| [docs/clients.md](docs/clients.md) | connecting Claude, Cursor, VS Code, OpenHands, and others |
| [docs/architecture.md](docs/architecture.md) | module boundaries, request flow |
| [docs/oauth.md](docs/oauth.md) | PKCE flow, token lifecycle, scopes, app registration |
| [docs/security.md](docs/security.md) | trust model, token storage, limitations |
| [docs/development.md](docs/development.md) | structure, CI, releases |
| [docs/testing.md](docs/testing.md) | test strategy, per-layer seams, conventions |
| [docs/adr/](docs/adr/) | architecture decision records |

## Development

```sh
uv sync
uv run pre-commit install
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
```

CI runs the same gate (with `uv sync --frozen`) plus a gitleaks secret scan on
every push/PR to `main`. Contribution guidelines: [CONTRIBUTING.md](CONTRIBUTING.md).
Releases follow SemVer with notes in [CHANGELOG.md](CHANGELOG.md).

## Architecture (short version)

```
cli/  mcp/ -> tools/ -> services/ -> repository/ (Protocol, atomic ops only) -> api/ -> auth/
                          models/, utils/, exceptions/, config/ are leaves
```

Services are transport-agnostic (explicit ids only; reference parsing lives
at the CLI/MCP boundary), the repository exposes atomic Spotify API
operations only (no workflow logic), and a single capability registry
(`tools/capabilities.py`) drives MCP annotations, the OAuth scope list, and
documentation. Full rationale in [docs/architecture.md](docs/architecture.md)
and the ADRs.

### Note on history

Commit history before the rewrite contains a Spotify client credential pair.
It has been rotated and is dead; the `legacy` branch preserves that history
intentionally. See [docs/security.md](docs/security.md).
