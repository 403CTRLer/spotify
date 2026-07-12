# Spotify Web API coverage matrix

Audited 2026-07-12 against the official reference and the
[Nov 27, 2024 platform announcement](https://developer.spotify.com/blog/2024-11-27-changes-to-the-web-api),
which restricts several endpoints for apps **without extended access** (this
app is a standard development-mode app, so those endpoints would return 403).

Legend: ✅ implemented · ➖ intentionally omitted · 🚫 restricted/deprecated for
this app class (cannot be implemented).

## Albums

| Endpoint | Status | Notes / scope |
|---|---|---|
| Get Album | ✅ `lookup` | none (public catalog) |
| Get Several Albums | ➖ | batch variant; `lookup` covers the single-item need |
| Get Album Tracks | ✅ internal (`mix` sources) | none |
| Get/Save/Remove/Check Saved Albums | ➖ | album library management is a niche beside track library; no user demand yet |
| Get New Releases | ➖ | browse/editorial surface, weak fit for a personal tool; `search` covers discovery |

## Artists

| Endpoint | Status | Notes / scope |
|---|---|---|
| Get Artist | ✅ `lookup` | none |
| Get Several Artists | ➖ | batch variant of the above |
| Get Artist's Albums | ➖ | `search --type album` covers the common case |
| Get Artist's Top Tracks | ➖ | playing an artist ref plays their context already; add on demand |
| Get Related Artists | 🚫 | restricted Nov 2024 |

## Tracks

| Endpoint | Status | Notes / scope |
|---|---|---|
| Get Track | ✅ `lookup` | none |
| Get Several Tracks | ➖ | batch variant |
| Get Saved Tracks | ✅ `library_tracks` / `liked-to-playlist` | user-library-read |
| Save Tracks | ✅ `save_to_library` / `like` | user-library-modify |
| Remove Saved Tracks | ✅ `remove_from_library` / `unlike`, `clear-liked` | user-library-modify |
| Check Saved Tracks | ➖ | contains-check; `library_tracks` pagination covers it, no caller yet |
| Get Audio Features / Analysis | 🚫 | restricted Nov 2024 |
| Get Recommendations | 🚫 | restricted Nov 2024 |

## Playlists

| Endpoint | Status | Notes / scope |
|---|---|---|
| Get Playlist | ✅ `lookup` / internals | playlist-read-private |
| Change Playlist Details | ✅ `update_playlist` / `update-playlist` | playlist-modify-* |
| Get Playlist Items | ✅ `playlist_items` / `tracks` | playlist-read-private |
| Add Items | ✅ `add_to_playlist` (chunked 100/request per the documented limit) | playlist-modify-* |
| Remove Items | ✅ `remove_from_playlist` | playlist-modify-* |
| Update Items (reorder) | ✅ atomic single-item reorder, driving `shuffle_playlist` (Fisher-Yates in the service layer, ~N calls) | playlist-modify-* |
| Update Items (replace) | ➖ | not needed once shuffle is reorder-based; would only serve a future bulk-replace tool |
| Get Current User's Playlists | ✅ `playlists` | playlist-read-private |
| Get User's Playlists (other users) | ➖ | me-focused tool; no use case |
| Create Playlist | ✅ `create_playlist` | playlist-modify-* |
| Unfollow Playlist (= delete own) | ✅ `delete_playlist` (confirm-gated) | playlist-modify-* |
| Follow Playlist | ➖ | following others' playlists: no demand yet, trivial to add |
| Get/Upload Custom Cover Image | ➖ | base64 JPEG upload + ugc-image-upload scope for a cosmetic feature |
| Get Featured / Category Playlists | 🚫 | restricted Nov 2024 |

## Player (all control endpoints require Spotify Premium)

| Endpoint | Status | Notes / scope |
|---|---|---|
| Get Playback State | ✅ `playback_state` / `now` | user-read-playback-state |
| Get Available Devices | ✅ (bundled into `playback_state`) | user-read-playback-state |
| Get Currently Playing Track | ➖ | strict subset of Get Playback State; one fewer tool for the same information |
| Start/Resume Playback | ✅ `play` | user-modify-playback-state |
| Pause Playback | ✅ `pause` | user-modify-playback-state |
| Skip Next / Previous | ✅ `skip_next`/`skip_previous`, `next`/`prev` | user-modify-playback-state |
| Add to Queue | ✅ `queue_add` / `queue` | user-modify-playback-state |
| Set Volume | ✅ `set_volume` / `volume` | user-modify-playback-state |
| Transfer Playback | ➖ | `play --device` covers switching-with-playback; pure transfer is niche |
| Seek / Repeat / Toggle Shuffle-mode | ➖ | remote-control minutiae with no LLM/CLI demand yet; trivial to add |
| Get the User's Queue | ➖ | read-only queue view; add on demand |
| Get Recently Played | ✅ `recent_history` / `recent` | user-read-recently-played |

## Users / Personalization

| Endpoint | Status | Notes / scope |
|---|---|---|
| Get Current User's Profile | ✅ `user_profile` | (basic profile; email scope deliberately not requested) |
| Get User's Top Items | ✅ `top_items` / `top` | user-top-read |
| Get User's Profile (by id) | ➖ | me-focused tool |
| Follow/Unfollow Artists or Users, Followed Artists, Check Follows | ➖ | social-graph features outside the library/playlist/playback focus |
| Follow/Unfollow Playlist | see Playlists | |

## Shows / Episodes / Audiobooks / Chapters

All ➖ — podcast and audiobook surfaces are outside this project's music
focus. The architecture supports them (new repository methods + tools) if
that changes.

## Categories / Genres / Markets

All ➖ — browse metadata with no consumer; genre seeds were part of the
restricted recommendations feature anyway.

## Scopes requested (10)

`playlist-read-private`, `playlist-read-collaborative`,
`playlist-modify-public`, `playlist-modify-private`, `user-library-read`,
`user-library-modify`, `user-read-recently-played`,
`user-read-playback-state`, `user-modify-playback-state`, `user-top-read`.

Each scope is also declared per-tool in
[`tools/capabilities.py`](../src/spotify_mcp/tools/capabilities.py), the
single source of truth; a test asserts this table and that module never
drift apart.

Deliberately **not** requested: `user-read-email`, `user-read-private`,
`user-read-currently-playing` (its one consumer was removed as a strict
subset of `playback_state`), `ugc-image-upload`, `user-follow-*`,
`streaming`, `app-remote-control`.
