# MCP tool reference

Transport: stdio (`spotify-mcp serve`). All tools require prior authentication
via `spotify-mcp auth`; unauthenticated calls return an `isError` result with
the message `Not authenticated. Run 'spotify-mcp auth' first.` All errors
(auth, not-found, rate-limit, validation) surface as `isError` results with
actionable messages - tools never crash the server.

Common types:

- **ref** (string): Spotify URL, `spotify:` URI, or bare 22-char ID.
- **Page envelope**: `{"total": int, "offset": int, "items": [...]}`. `total`
  is the remote total and can exceed `len(items)` when null/local entries were
  filtered.
- **Track**: `{"id": str|null, "uri": str, "name": str, "artists": [str],
  "album": str|null, "duration_ms": int, "is_local": bool}`
- **Playlist**: `{"id": str, "uri": str, "name": str, "owner_id": str,
  "public": bool|null, "collaborative": bool, "total_tracks": int,
  "description": str|null}`

---

### `user_profile()`
Returns `{"id": str, "display_name": str|null}`.

### `currently_playing()`
Returns `{"is_playing": bool, "progress_ms": int|null, "track": Track}` or the
string `"Nothing is playing."` when the player is idle (never an error).

### `playlists(limit: int = 50, offset: int = 0)`
Page envelope of Playlist objects (owned and followed). `limit` clamped to 1-50.

### `playlist_items(playlist: ref, limit: int = 100, offset: int = 0)`
Page envelope of Track objects. `limit` clamped to 1-100. Track refs must be
playlists; a track/album URL raises a validation error.

### `search(query: str, types: list[str]|null = null, limit: int = 10)`
`types` defaults to `["track"]`; may include `track`, `playlist`, `album`,
`artist`. Returns a dict keyed by plural type name (`"tracks"`, `"playlists"`,
`"albums"`, `"artists"`); tracks/playlists are full objects as above, other
types are `{"id", "name", "uri"}`. `limit` clamped to 1-50.

### `create_playlist(name: str, description: str = "", public: bool = false)`
Creates a playlist owned by the current user; returns the Playlist object.

### `add_to_playlist(playlist: ref, tracks: list[ref])`
Adds tracks (chunked at 100 per request). Returns `"Added N tracks."`.

### `remove_from_playlist(playlist: ref, tracks: list[ref])`
Removes **all occurrences** of the given tracks. Returns `"Removed N tracks."`.

### `library_tracks(limit: int = 50, offset: int = 0)`
Page envelope of the user's saved (liked) tracks. `limit` clamped to 1-50.

### `recent_history(limit: int = 20)`
List of `{"played_at": str|null, "track": Track}`, most recent first.
`limit` clamped to 1-50 (API maximum).

---

Not exposed as tools (CLI-only, destructive or long-running): shuffle,
shuffle-all, mix, liked-to-playlist, clear-liked, restore. Exposing writes of
that magnitude to an LLM caller is a deliberate non-goal for now.
