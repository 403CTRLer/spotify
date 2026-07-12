# Developer guide

## Project structure

See [architecture.md](architecture.md) for boundaries and flow. Quick map:

```
src/spotify_mcp/
  config/      Settings (env > ./.env > ~/.spotify-mcp/.env)
  exceptions/  SpotifyMcpError family
  utils/       links.parse_ref (pure parser), logging setup
  models/      pydantic Playlist/Track/User + Page/PlayedItem TypedDicts
  auth/        PKCE flow + token cache (thread + cross-process locked refresh)
  api/         SpotifyApiClient (HTTP mechanics)
  repository/  SpotifyRepository protocol + Web API implementation (atomic ops only)
  services/    business logic and workflows (SpotifyService; explicit ids only)
  tools/       MCP tool adapters + capabilities.py (capability registry)
  mcp/         FastMCP server (annotations + instructions from the registry)
  cli/         argparse subcommands (resolves references at the boundary)
tests/         one file per layer + test_links/test_config/test_capabilities
docs/          this documentation, ADRs in docs/adr/
```

## Setup

```sh
uv sync                    # creates .venv from uv.lock
uv run pre-commit install  # ruff + ruff-format + gitleaks on commit
```

## Testing

```sh
uv run pytest -q                       # full suite (~2s, no network)
```

Strategy, per-layer seams, and conventions: [testing.md](testing.md).

## Quality gate (run before every commit; CI runs the same)

```sh
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest -q
```

## CI

`.github/workflows/ci.yml`: `uv sync --frozen --dev` (lockfile drift fails the
build) then the gate above, plus a gitleaks job. Actions are pinned to commit
SHAs with the tag in a trailing comment - bump by updating the SHA, not the tag.

## Release process

1. Update `version` in `pyproject.toml` (SemVer; pre-1.0 minor bumps may break).
2. Move `[Unreleased]` CHANGELOG entries under the new version with the date.
3. Commit, tag `vX.Y.Z`, push with tags. (No package publishing currently.)

## Adding a feature (checklist)

1. New remote data needs an **atomic** `SpotifyRepository` protocol method +
   `SpotifyApiRepository` implementation - one method per API operation, no
   sequencing or algorithms at this layer.
2. Business logic and any orchestration goes in `SpotifyService`, taking
   explicit identifiers only (never a URL/URI - see architecture.md).
3. To expose it as an MCP tool: add the thin adapter in `tools/definitions.py`
   (it resolves references via `utils.links.parse_ref` and calls the
   service), then add its entry to `tools/capabilities.py` (read_only,
   destructive, idempotent, confirmation_required, scopes) - a test fails if
   the registry and the tool list drift apart. Destructive tools need the
   confirm protocol (see ADR 0005).
4. Add or extend a CLI subcommand if it's useful outside an LLM context.
5. Tests at the layer that owns the logic; update the tool reference, user
   guide, api-coverage matrix, and CHANGELOG when behavior changes.
