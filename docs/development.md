# Developer guide

## Project structure

See [architecture.md](architecture.md) for boundaries and flow. Quick map:

```
src/spotify_mcp/
  config/      Settings (env > ./.env > ~/.spotify-mcp/.env)
  exceptions/  SpotifyMcpError family
  utils/       links.parse_ref, logging setup
  models/      pydantic Playlist/Track/User + Page/NowPlaying/PlayedItem TypedDicts
  auth/        PKCE flow + token cache
  client/      SpotifyApiClient (HTTP mechanics)
  repository/  SpotifyRepository protocol + Web API implementation
  services/    business logic (SpotifyService)
  tools/       MCP tool adapters
  mcp/         FastMCP server
  cli/         argparse subcommands
tests/         one file per layer + test_links/test_config
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
uv run pytest tests/test_services.py   # one layer
```

Conventions:

- **Service tests** use the in-memory `FakeRepo` (structural match of the
  protocol - pyright enforces it). No HTTP stubbing at this layer.
- **Repository/client tests** use `httpx.MockTransport`; handlers route on
  URL params, never on path alone (pagination follows same-path `next` URLs).
- **Auth tests** monkeypatch `_token_request`/`_await_callback`; the PKCE
  challenge is pinned to the RFC 7636 Appendix B vector.
- Every bug fix lands with a regression test referencing its review item.

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

1. Business logic goes in `SpotifyService` against the protocol; new remote
   data needs a protocol method + `SpotifyApiRepository` implementation.
2. Expose via a thin CLI handler and/or tool function; only `cli/` may
   print/prompt.
3. Destructive playlist operations must snapshot before mutating
   (see [recovery.md](recovery.md)) and respect the local-tracks guard.
4. Tests at the layer that owns the logic; update the tool reference and
   CHANGELOG when behavior changes.
