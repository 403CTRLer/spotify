# Changelog

All notable changes to this project are documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-07-12

Production-readiness release: playback support, full API audit, destructive
MCP tools behind a confirm protocol, and the remaining reliability debt paid.

### Action required

- **Re-run `spotify-mcp auth`**: scopes grew from 8 to 11
  (`user-read-playback-state`, `user-modify-playback-state`, `user-top-read`).
  The cached token is rejected with an actionable message until re-consent.

### Added

- **Playback** (Spotify Premium required for control): `now`, `play`,
  `pause`, `next`, `prev`, `queue`, `volume` CLI commands and
  `playback_state`, `play`, `pause`, `skip_next`, `skip_previous`,
  `queue_add`, `set_volume` MCP tools. (ADR 0004)
- **Personalization & lookup**: `top` / `top_items` (short/medium/long
  ranges), `lookup` for any Spotify link, `search`, `tracks`, `recent` CLI
  commands.
- **Library**: `like`/`unlike` CLI, `save_to_library`/`remove_from_library`
  tools (PUT /me/tracks).
- **Playlist management**: `create-playlist`, `update-playlist`
  (`--public`/`--private`), `delete-playlist` CLI; `update_playlist` tool and
  confirm-gated `delete_playlist`/`shuffle_playlist` tools - destructive MCP
  tools return a no-op preview until called with `confirm=true`. (ADR 0005)
- **CLI `--json`** flag for machine-readable output on read commands.
- Cross-process **file lock** around token refresh (msvcrt/flock) - the CLI
  and MCP server sharing one cache can no longer double-refresh and
  invalidate the rotating-refresh-token grant.
- `restore` **conflict detection**: refuses to discard tracks added after
  the snapshot unless `--force`.
- Docs: API coverage matrix (audited against the Nov 2024 platform
  restrictions), OAuth guide, testing guide, ADRs 0004/0005.

### Fixed

- **CI secrets job failed on every run**: shallow checkout broke gitleaks'
  range scan. Now a deterministic full-history scan with the single known
  (rotated) historical credential pinned in `.gitleaksignore`.

### Intentionally omitted (documented in docs/api-coverage.md)

- Recommendations, audio features/analysis, related artists, featured/
  category playlists: restricted by Spotify (Nov 2024) for this app class.
- Shows/episodes/audiobooks, follow graph, saved albums, seek/repeat/
  transfer, cover upload: no consumer yet; each is a small addition when
  demand appears.

## [0.2.0] - 2026-07-11

Hardening release addressing an internal staff-level review (items #1-#15).
Two behavior changes are breaking in the everyday sense; both exist to stop
silent data loss.

### Changed (behavioral)

- **`shuffle` refuses playlists containing local/unavailable tracks** instead
  of silently and permanently dropping them (the Web API cannot re-add them).
  `spotify-mcp shuffle --force` shuffles only the streamable tracks and
  records the dropped entries in the recovery snapshot. `shuffle-all` skips
  such playlists with a `skipped` status. (review #1, ADR 0002)
- **`mix` is additive-only.** It no longer removes mixed tracks from the
  target before re-adding: existing copies keep their position, only new
  tracks are appended (shuffled), and nothing is ever removed - eliminating
  the partial-failure data-loss window. Duplicate counts now include overlap
  with the target. (review #2, ADR 0001)
- Rate limiting: when Spotify requests a wait longer than the 30s cap, calls
  fail immediately with the wait time attached instead of burning retries
  that were guaranteed to fail. (review #5)
- `.env` resolution falls back to `~/.spotify-mcp/.env` when the working
  directory has none. (review #12)
- Page `limit` arguments are clamped to each endpoint's documented maximum
  instead of surfacing Spotify 400s. (review #13)

### Added

- `spotify-mcp restore <snapshot.json>` applies a recovery snapshot and
  deletes it on success. (review #6)
- `spotify-mcp shuffle --force`. (review #1)
- Documentation set: user guide, MCP tool reference, architecture, recovery,
  security, developer guide, and ADRs under `docs/`.

### Fixed

- Token refresh is serialized and reuse-detecting: concurrent refreshes
  (worker threads, or CLI + server sharing the cache) no longer present the
  same rotated refresh token, which could invalidate the grant. (review #3)
- Network failures during token requests, malformed token caches, and
  API items without ids now raise typed, actionable errors instead of raw
  httpx/KeyError tracebacks. (review #4)
- Non-numeric `Retry-After` headers no longer crash the client. (review #5)
- The OAuth callback server ignores stray requests (favicon probes) instead
  of failing the login, and reports a busy port as an actionable error.
  (review #9)
- `shuffle-all --ignore` no longer accumulates values across repeated parser
  invocations (argparse shared-default pitfall). (review #10)
- `clear-liked` treats closed stdin (EOF) as refusal instead of crashing.
  (review #15)
- `serve` respects `-v`/`-vv` instead of hardcoding INFO. (review #11)

### Internal

- `SpotifyRepository` envelopes are typed (`Page[T]`, `NowPlaying`,
  `PlayedItem`); models flow to the tool boundary where they are dumped once.
  (review #7, ADR 0003)
- CI enforces the lockfile (`uv sync --frozen`) and pins GitHub Actions to
  commit SHAs. (review #8)
- Tool-level and CLI-level test suites added; 105 tests total. (review #15)

## [0.1.0] - 2026-07-11

Complete rewrite. The original script-based project is preserved on the
`legacy` branch.

### Added

- OAuth Authorization Code + PKCE auth (`auth/`): no client secret, rotating
  refresh tokens, atomic token cache in `~/.spotify-mcp/`.
- `SpotifyApiClient` (`client/`): httpx with 401 refresh-retry, 429
  Retry-After backoff, pagination; typed exception family (`exceptions/`).
- `SpotifyRepository` protocol + Web API implementation (`repository/`) with
  pydantic models for Playlist/Track/User (`models/`).
- `SpotifyService` (`services/`): mix, shuffle (snapshot-before-mutation
  recovery), shuffle-all with ignore list, liked-songs workflows.
- MCP server (`mcp/`, `tools/`) exposing 10 provider-agnostic tools over stdio.
- Developer CLI (`cli/`): auth, serve, playlists, mix, shuffle, shuffle-all,
  liked-to-playlist, clear-liked.
- Tooling: uv + lockfile, ruff, pyright, pytest (71 tests), pre-commit with
  gitleaks, GitHub Actions CI.

### Fixed (vs legacy)

- Empty ignore list no longer ignores every playlist in shuffle-all.
- Spotify URI (`spotify:playlist:...`) and URL parsing share one correct parser.
- Shuffle can no longer lose tracks: full snapshot is written before any
  mutation and replace-PUT removes the empty-playlist window.
- Deleting liked songs requires a strict confirmation and no longer reports
  false success on refusal.
- Null/local tracks in playlists no longer crash extraction.
- Menu `KeyError` crashes replaced by argparse validation.

### Security

- Credentials moved to `.env` (gitignored); the client secret that existed in
  pre-rewrite git history must be rotated on the Spotify dashboard.
