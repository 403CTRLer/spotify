# MCP tool reference

Transport: stdio (`spotify-mcp serve`). Every tool requires prior
authentication (`spotify-mcp auth`); unauthenticated or failed calls return an
`isError` result with an actionable message - tools never crash the server.
Each tool's exact `read_only` / `destructive` / `idempotent` behavior and
required OAuth scope are declared in one place,
[`tools/capabilities.py`](../src/spotify_mcp/tools/capabilities.py), and
surfaced to clients as MCP `ToolAnnotations`.

Common types:

- **ref** (string, tool parameters only): Spotify URL, `spotify:` URI, or
  bare 22-char ID where the parameter names the type.
- **Page envelope**: `{"total": int, "offset": int, "items": [...]}`.
- **Track**: `{"id": str|null, "uri": str, "name": str, "artists": [str],
  "album": str|null, "duration_ms": int, "is_local": bool}`
- **Playlist**: `{"id": str, "uri": str, "name": str, "owner_id": str,
  "public": bool|null, "collaborative": bool, "total_tracks": int,
  "description": str|null}`

## Confirm protocol (destructive tools)

Tools with `confirmation_required` in the registry take `confirm: bool =
false`. Called without it, they return a preview naming the target and scale
and make **no changes**; call again with `confirm=true` to execute.
Rationale: [ADR 0005](adr/0005-destructive-tool-confirm-protocol.md).

---

## Authentication

Handled entirely outside the MCP surface: run `spotify-mcp auth` once in a
terminal (opens a browser for the PKCE login). No tool performs auth. See
[oauth.md](oauth.md).

## User Profile

- **`user_profile()`** - the authenticated user's id and display name.

## Search

- **`search(query, types=null, limit=10)`** - `types` defaults to `["track"]`;
  may include `track`, `playlist`, `album`, `artist`. Returns a dict keyed by
  plural type name.
- **`lookup(ref)`** - metadata for any Spotify URL/URI (track, album, artist,
  or playlist), dispatched by type. Bare IDs are rejected here (ambiguous).

## Library

- **`library_tracks(limit=50, offset=0)`** - saved tracks, paged.
- **`save_to_library(tracks: [ref])`** - like tracks.
- **`remove_from_library(tracks: [ref])`** - unlike tracks.
- **`recent_history(limit=20)`** - `[{"played_at": str|null, "track": Track}]`.
- **`top_items(kind="tracks", time_range="medium", limit=20)`** - the user's
  most-listened tracks or artists. `time_range`: `short` (~4 weeks), `medium`
  (~6 months), `long` (years).

## Playlists

- **`playlists(limit=50, offset=0)`** - the user's playlists, paged.
- **`playlist_items(playlist: ref, limit=100, offset=0)`** - tracks in a
  playlist, paged.
- **`create_playlist(name, description="", public=false)`**
- **`add_to_playlist(playlist: ref, tracks: [ref])`**
- **`remove_from_playlist(playlist: ref, tracks: [ref])`** - removes all
  occurrences of each track.
- **`update_playlist(playlist: ref, name=null, description=null,
  public=null)`** - changes only the provided fields.
- **`delete_playlist(playlist: ref, confirm=false)`** - confirm protocol.
  Unfollows the playlist (deletion, for owned playlists); Spotify keeps it
  recoverable for ~90 days via the account page.
- **`shuffle_playlist(playlist: ref, confirm=false)`** - confirm protocol.
  Reorders every track **in place** (no track is ever removed or re-added,
  so nothing can be lost); costs about one API request per track.

## Playback

Control tools require a **Spotify Premium** account (403 otherwise).

- **`playback_state()`** - current state (track, device, shuffle/repeat) and
  available devices; `state` is null when nothing is playing.
- **`play(item=null, device_id=null)`** - resume, or play a track/album/
  playlist/artist. `item` must be a URL or URI here (bare IDs are ambiguous).
- **`pause()`**, **`skip_next()`**, **`skip_previous()`**
- **`queue_add(track: ref)`**
- **`set_volume(percent)`** - 0-100.

---

## Not exposed as tools

- `clear-liked` (delete ALL saved tracks): irreversible with no MCP use case
  strong enough to justify the risk. CLI-only, behind a strict prompt.
- `mix` / `liked-to-playlist`: long-running batch workflows better suited to
  a terminal; their building blocks (`add_to_playlist`, `library_tracks`) are
  exposed as tools.
- Endpoints intentionally not implemented at all (recommendations, audio
  features, related artists, etc.): [api-coverage.md](api-coverage.md).
