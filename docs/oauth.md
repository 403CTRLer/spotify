# OAuth guide

## Flow: Authorization Code + PKCE (RFC 7636)

There is **no client secret** anywhere in this project. The app authenticates
with a public client ID plus a per-login proof-of-possession:

```
spotify-mcp auth
  │ 1. generate code_verifier (secrets.token_urlsafe(64))
  │    derive code_challenge = BASE64URL(SHA256(verifier)), state token
  │ 2. open browser → accounts.spotify.com/authorize
  │       ?client_id&response_type=code&redirect_uri&state
  │       &scope=<10 scopes>&code_challenge_method=S256&code_challenge
  │ 3. loopback http.server on 127.0.0.1:8888 waits (300s max) for
  │    GET /callback?code&state   ← only this exact path with code/error
  │    params is accepted; state mismatch aborts
  │ 4. POST accounts.spotify.com/api/token
  │       grant_type=authorization_code + code + code_verifier
  └─ 5. tokens cached at ~/.spotify-mcp/tokens.json (atomic write)
```

The MCP server **never** runs this flow: a client-spawned stdio process
cannot pop a browser reliably, and stdout is the protocol channel. It raises
`AuthError("Not authenticated. Run 'spotify-mcp auth' first.")` instead.

## Token lifecycle

- Access tokens live ~1 hour; refreshed automatically 60s before expiry, or
  once after an unexpected 401.
- Spotify **rotates refresh tokens** on every refresh. Presenting an
  already-used refresh token can invalidate the whole grant, so refresh is
  serialized twice over:
  1. a `threading.Lock` (FastMCP worker threads in one process),
  2. a cross-process file lock on `~/.spotify-mcp/tokens.lock`
     (`msvcrt` on Windows, `flock` elsewhere).
  Inside the lock the cache is re-read; if another actor already refreshed,
  its token is reused. On lock timeout (15s) refresh proceeds unlocked with a
  warning - a rare double refresh beats a deadlock.
- If the refresh response omits a new refresh token, the previous one is kept.
- A cached token missing any currently-required scope triggers an actionable
  "run spotify-mcp auth" error - this is how scope changes (additions or, as
  in 0.4.0, a removal) force a clean re-consent instead of mysterious 403s.

## Scopes

See the table in [api-coverage.md](api-coverage.md#scopes-requested-10) - 10
scopes, each declared against the tool that needs it in
[`tools/capabilities.py`](../src/spotify_mcp/tools/capabilities.py) (the
single source of truth) and checked by an automated test. Profile/email,
follow, image-upload, and streaming scopes are deliberately not requested.

## App registration requirements

- Redirect URI must be registered **exactly** as
  `http://127.0.0.1:8888/callback`. Spotify rejects `http://localhost` for
  apps created after April 2025, and the loopback server binds only
  `127.0.0.1`.
- Playback *control* (play/pause/skip/queue/volume) additionally requires the
  Spotify account to be **Premium** - the API returns 403 otherwise.
- Development-mode apps have tight rate limits; see the retry policy in
  [architecture.md](architecture.md).
