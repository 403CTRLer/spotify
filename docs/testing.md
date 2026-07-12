# Testing guide

## Running

```sh
uv run pytest -q                     # full suite, ~2s, zero network
uv run pytest tests/test_services.py -q
uv run pytest -q -k "shuffle"        # by keyword
```

The full local gate (identical to CI):

```sh
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest -q
```

## Strategy: one seam per layer

| Layer | Seam | How |
|---|---|---|
| `utils/links`, `config` | pure functions | table-driven parametrize |
| `auth` | `_token_request`, `_await_callback` monkeypatched | PKCE challenge pinned to the RFC 7636 Appendix B vector; cache via `tmp_path`; concurrency via real threads + events |
| `api` | `httpx.MockTransport` | one test per status path (401 refresh, 429 backoff/fail-fast, 404, 204, transport errors), pagination |
| `repository` | `httpx.MockTransport` | request shapes (method/path/params/body), chunk sizes, payload trimming, null filtering; reorder body/snapshot_id threading |
| `services` | in-memory `FakeRepo` | business rules and workflows: shuffle permutation correctness (including a planted local-track URI), optimistic-concurrency snapshot_id threading, mix additivity, kind validation, counts. pyright enforces that FakeRepo structurally satisfies `SpotifyRepository` - protocol drift fails the typecheck, not just tests. Services are called with explicit ids only - no reference parsing here |
| `tools` | stub service via `monkeypatch` | branch logic and the reference-resolution boundary: confirm protocol, kind validation, model dumping, that refs are normalized to ids before reaching the service |
| `cli` | stub `_service` + `capsys` | flag wiring, --json output, confirmation refusals, exit codes, boundary normalization (bare id -> track in `play`, rejection in `mix`) |
| `mcp` | `build_server()` | the registered tool set and their `ToolAnnotations` match `tools/capabilities.py` exactly; server instructions are present |
| `tools/capabilities.py` | direct assertions | registry <-> tool list is 1:1; requested OAuth scopes equal the union of declared scopes (fails on drift); confirmation_required tools (and only those) accept a `confirm` parameter |

## Conventions

- **Every bug fix lands with a regression test** naming its review item in a
  comment (`# review #N: ...`).
- Mock handlers route on **URL params, never path alone** - pagination
  follows `next` URLs with identical paths, and a path-routed handler loops
  forever (this bit us once).
- Concurrency tests use events/barriers, not bare sleeps, to stay
  deterministic; the one deliberate sleep holds a lock long enough for the
  contender to block.
- No fixtures beyond `tmp_path`/`monkeypatch`/tiny local classes; no network,
  no VCR cassettes, no snapshot testing.
- Destructive-path tests always assert the negative too: refusal ⇒ zero
  mutating calls and no stray files.

## What is deliberately not tested

- The interactive browser flow (`login()`'s webbrowser/HTTP plumbing) - thin
  stdlib glue, exercised manually via `spotify-mcp auth`.
- Live Spotify calls - the request shapes are asserted against MockTransport;
  the contract with the real API is validated by usage.
