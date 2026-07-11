# MCP tool reference

Transport: stdio (`spotify-mcp serve`). 24 tools. All require prior
authentication via `spotify-mcp auth`; unauthenticated calls return an
`isError` result with `Not authenticated. Run 'spotify-mcp auth' first.`
All errors (auth, not-found, rate-limit, Premium-required 403s, validation)
surface as `isError` results with actionable messages - tools never crash
the server.

Common types:

- **ref** (string): Spotify URL, `spotify:` URI, or bare 22-char ID.
- **Page envelope**: `{"total": int, "offset": int, "items": [...]}`. `total`
  is the remote total and can exceed `len(items)` when null/local entries
  were filtered.
- **Track**: `{"id": str|null, "uri": str, "name": str, "artists": [str],
  "album": str|null, "duration_ms": int, "is_local": bool}`
- **Playlist**: `{"id": str, "uri": str, "name": str, "owner_id": str,
  "public": bool|null, "collaborative": bool, "total_tracks": int,
  "description": str|null}`
- **Artist summary**: `{"id", "name", "uri", "genres": [str],
  "popularity": int|null, "followers": int|null}`
- **Device**: `{"id", "name", "type", "is_active": bool,
  "volume_percent": int|null}`

## Confirm protocol (destructive tools)

`delete_playlist` and `shuffle_playlist` take `confirm: bool = false`.
Called without it, they return a `CONFIRMATION REQUIRED` preview naming the
target and scale and **make no changes**; call again with `confirm=true` to
execute. Rationale: [ADR 0005](adr/0005-destructive-tool-confirm-protocol.md).

---

## Reads

### `user_profile()`
`{"id": str, "display_name": str|null}`.

### `currently_playing()`
`{"is_playing": bool, "progress_ms": int|null, "track": Track}` or the string
`"Nothing is playing."` (never an error).

### `playback_state()`
`{"state": {...}|null, "devices": [Device]}`. `state` holds `is_playing`,
`progress_ms`, `shuffle_state`, `repeat_state`, `device` (Device), and
`track` (Track|null); null when the player is idle.

### `playlists(limit=50, offset=0)` → Page of Playlist
### `playlist_items(playlist: ref, limit=100, offset=0)` → Page of Track
### `library_tracks(limit=50, offset=0)` → Page of Track
### `recent_history(limit=20)` → `[{"played_at": str|null, "track": Track}]`

### `top_items(kind="tracks", time_range="medium", limit=20)`
The user's most-listened items. `kind`: `tracks` (Page of Track) or `artists`
(Page of Artist summary). `time_range`: `short` (~4 weeks), `medium`
(~6 months), `long` (years).

### `search(query, types=null, limit=10)`
`types` defaults to `["track"]`; may include `track`, `playlist`, `album`,
`artist`. Returns a dict keyed by plural type name; tracks/playlists are full
objects, others `{"id", "name", "uri"}`.

### `lookup(ref)`
Metadata for any Spotify URL/URI, dispatched by type; result carries
`"type": "track"|"album"|"artist"|"playlist"` plus the object fields
(albums: `{"id","name","uri","artists","release_date","total_tracks","label"}`).
Bare IDs are rejected (ambiguous type).

## Playback control (Spotify Premium required; 403 otherwise)

### `play(item=null, device_id=null)`
Resume, or play a reference. Tracks play directly; album/playlist/artist
refs play as a context. Bare IDs are assumed to be tracks. `device_id` (from
`playback_state`) targets a device.

### `pause()` · `skip_next()` · `skip_previous()`
Act on the active device.

### `queue_add(track: ref)`
Appends a track to the queue.

### `set_volume(percent: int)`
0-100; validated before the API call.

## Library writes

### `save_to_library(tracks: [ref])` / `remove_from_library(tracks: [ref])`
Like/unlike tracks; chunked at 50 per request. Additive/reversible - no
confirm needed.

## Playlist writes

### `create_playlist(name, description="", public=false)` → Playlist
### `add_to_playlist(playlist: ref, tracks: [ref])` → "Added N tracks."
### `remove_from_playlist(playlist: ref, tracks: [ref])`
Removes **all occurrences** of each track.

### `update_playlist(playlist: ref, name=null, description=null, public=null)`
Changes only the provided fields; providing none is a validation error.

### `delete_playlist(playlist: ref, confirm=false)` — confirm protocol
Unfollows the playlist (= deletion for owned playlists). Spotify keeps
deleted playlists recoverable for ~90 days via the account page.

### `shuffle_playlist(playlist: ref, confirm=false, force=false)` — confirm protocol
Persistently reorders the playlist. A full recovery snapshot is written
before any change (see [recovery.md](recovery.md)). Playlists containing
local/unavailable tracks are refused unless `force=true` (those entries
would be permanently lost and are recorded in the snapshot).

---

## Not exposed as tools, and why

- `clear-liked` (delete ALL saved tracks): irreversible, snapshot-less; no
  MCP use case justifies it. CLI-only behind a strict prompt.
- `mix` / `shuffle-all` / `liked-to-playlist` / `restore`: long-running batch
  workflows better suited to a terminal; their building blocks
  (`add_to_playlist`, `shuffle_playlist`, `library_tracks`) are exposed.
- Seek/repeat/shuffle-mode/transfer/queue-read: see
  [api-coverage.md](api-coverage.md) - added when demand appears.
