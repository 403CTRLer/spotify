# Security

## OAuth model

- **Authorization Code + PKCE** (RFC 7636, S256). There is **no client
  secret anywhere**: `.env` holds only the public client ID and redirect URI.
  A leaked `.env` grants nothing by itself.
- The browser flow runs only in `spotify-mcp auth`. The MCP server never opens
  a browser or listens on the network; unauthenticated tool calls fail with an
  actionable `AuthError`.
- The loopback callback server binds `127.0.0.1` only, accepts **only** the
  registered redirect path carrying `code`/`error` parameters (everything else
  gets a 404 and the wait continues), validates the OAuth `state` value, and
  times out after 300s.
- Scopes are trimmed to the 11 the tools actually use (playlist read/modify,
  library read/modify, currently-playing, recently-played, playback
  read/modify, top items). No follow, no email/profile, no image-upload
  scopes. Full mapping: [oauth.md](oauth.md) and
  [api-coverage.md](api-coverage.md).

## Token storage

- Cache: `~/.spotify-mcp/tokens.json`, written atomically (temp file +
  `os.replace`), `chmod 0o600` applied best-effort.
- **Known limitation (review #14, accepted):** the refresh token is stored in
  **plaintext**, and on Windows `chmod` does not narrow ACLs - protection is
  whatever the user-profile directory grants. The trust model is a
  single-user machine; any process running as you can read the token. Moving
  to `keyring` (DPAPI/Keychain/SecretService) is the upgrade path if that
  model ever stops holding; it was deliberately not added now to avoid a new
  dependency for a personal tool.
- A malformed cache is treated as "not authenticated", never trusted.

## Refresh behavior

- Access tokens are refreshed 60s before expiry, or after a 401 (once).
- Spotify **rotates refresh tokens**. Refreshes are serialized behind a
  thread lock AND a cross-process file lock (`~/.spotify-mcp/tokens.lock`,
  msvcrt/flock); inside the locks the cache is re-read, and a fresh token
  written by another thread or process is **reused instead of refreshed
  again** - presenting an already-rotated refresh token can invalidate the
  whole grant family. Lock timeout (15s) degrades to an unlocked refresh
  with a warning rather than deadlocking.
- The new refresh token is persisted immediately; when the response omits one,
  the previous token is kept.
- Full lifecycle detail: [oauth.md](oauth.md).

## Repository history

Pre-rewrite commits (reachable from the `legacy` branch) contain a Spotify
client id/secret pair. That credential has been rotated and is dead; the
history is preserved deliberately. gitleaks runs in pre-commit (staged
changes) and CI (pushed state) to prevent recurrence; CI actions are pinned
to commit SHAs.

## Reporting

This is a personal project; report security issues via GitHub issues (or a
private channel if disclosure matters).
