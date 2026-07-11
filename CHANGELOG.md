# Changelog

All notable changes to this project are documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
