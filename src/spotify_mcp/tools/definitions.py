"""Provider-agnostic MCP tools. Thin adapters over SpotifyService.

Docstrings become tool descriptions; type hints become tool schemas.
Exceptions propagate - FastMCP converts them into isError results, and
AuthError messages tell the model/user to run `spotify-mcp auth`.
"""

from collections.abc import Mapping
from functools import lru_cache
from typing import Any

from spotify_mcp.auth.oauth import SpotifyAuth
from spotify_mcp.client.api_client import SpotifyApiClient
from spotify_mcp.config.settings import Settings
from spotify_mcp.repository.spotify import SpotifyApiRepository
from spotify_mcp.services.service import SpotifyService


@lru_cache(maxsize=1)
def get_service() -> SpotifyService:
    settings = Settings.from_env()
    repo = SpotifyApiRepository(SpotifyApiClient(SpotifyAuth(settings)))
    return SpotifyService(repo, recovery_dir=settings.recovery_dir)


def _page(page: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "total": page["total"],
        "offset": page["offset"],
        "items": [item.model_dump() for item in page["items"]],
    }


def user_profile() -> dict[str, Any]:
    """Get the authenticated user's profile (id and display name)."""
    return get_service().me().model_dump()


def currently_playing() -> dict[str, Any] | str:
    """Get the currently playing track, or a message when nothing is playing."""
    now = get_service().currently_playing()
    if not now:
        return "Nothing is playing."
    return {
        "is_playing": now["is_playing"],
        "progress_ms": now["progress_ms"],
        "track": now["track"].model_dump(),
    }


def playlists(limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """List the user's playlists (owned and followed), paged."""
    return _page(get_service().my_playlists(limit, offset))


def playlist_items(playlist: str, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """List tracks in a playlist, paged. Accepts a playlist URL, URI, or ID."""
    return _page(get_service().playlist_items(playlist, limit, offset))


def search(query: str, types: list[str] | None = None, limit: int = 10) -> dict[str, Any]:
    """Search the music catalog. types may include track, playlist, album, artist
    (default: track)."""
    return get_service().search(query, tuple(types) if types else ("track",), limit)


def create_playlist(name: str, description: str = "", public: bool = False) -> dict[str, Any]:
    """Create a new playlist owned by the current user."""
    return get_service().create_playlist(name, description, public).model_dump()


def add_to_playlist(playlist: str, tracks: list[str]) -> str:
    """Add tracks to a playlist. Both accept URLs, URIs, or IDs."""
    count = get_service().add_to_playlist(playlist, tracks)
    return f"Added {count} tracks."


def remove_from_playlist(playlist: str, tracks: list[str]) -> str:
    """Remove all occurrences of the given tracks from a playlist."""
    count = get_service().remove_from_playlist(playlist, tracks)
    return f"Removed {count} tracks."


def library_tracks(limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """List the user's saved (liked) tracks, paged."""
    return _page(get_service().saved_tracks(limit, offset))


def recent_history(limit: int = 20) -> list[dict[str, Any]]:
    """List recently played tracks with played_at timestamps (max 50)."""
    return [
        {"played_at": item["played_at"], "track": item["track"].model_dump()}
        for item in get_service().recently_played(limit)
    ]


# -- playback (requires Spotify Premium for control commands) ---------------------


def playback_state() -> dict[str, Any]:
    """Current playback state (track, device, shuffle/repeat) and the list of
    available devices. state is null when nothing is playing."""
    return get_service().playback()


def play(item: str | None = None, device_id: str | None = None) -> str:
    """Start or resume playback (Premium required). Without `item`, resumes.
    `item` may be a track/album/playlist/artist URL, URI, or bare track ID.
    `device_id` (from playback_state) targets a specific device."""
    return get_service().play(item, device_id)


def pause() -> str:
    """Pause playback on the active device (Premium required)."""
    get_service().pause()
    return "Paused."


def skip_next() -> str:
    """Skip to the next track (Premium required)."""
    get_service().skip_next()
    return "Skipped to next track."


def skip_previous() -> str:
    """Skip to the previous track (Premium required)."""
    get_service().skip_previous()
    return "Skipped to previous track."


def queue_add(track: str) -> str:
    """Add a track (URL, URI, or ID) to the playback queue (Premium required)."""
    get_service().queue_add(track)
    return "Added to queue."


def set_volume(percent: int) -> str:
    """Set playback volume, 0-100 (Premium required)."""
    get_service().set_volume(percent)
    return f"Volume set to {percent}%."


# -- personalization and lookup ------------------------------------------------------


def top_items(kind: str = "tracks", time_range: str = "medium", limit: int = 20) -> dict[str, Any]:
    """The user's most-listened tracks or artists. kind: 'tracks' or 'artists';
    time_range: 'short' (~4 weeks), 'medium' (~6 months), or 'long' (years)."""
    service = get_service()
    if kind == "tracks":
        return _page(service.top_tracks(time_range, limit))
    if kind == "artists":
        page = service.top_artists(time_range, limit)
        return {"total": page["total"], "offset": page["offset"], "items": page["items"]}
    raise ValueError("kind must be 'tracks' or 'artists'")


def lookup(ref: str) -> dict[str, Any]:
    """Metadata for any Spotify URL or URI (track, album, artist, or playlist)."""
    return get_service().lookup(ref)


# -- library ---------------------------------------------------------------------


def save_to_library(tracks: list[str]) -> str:
    """Save (like) tracks to the user's library. Accepts URLs, URIs, or IDs."""
    count = get_service().save_library_tracks(tracks)
    return f"Saved {count} tracks to your library."


def remove_from_library(tracks: list[str]) -> str:
    """Remove (unlike) tracks from the user's library. Accepts URLs, URIs, or IDs."""
    count = get_service().remove_library_tracks(tracks)
    return f"Removed {count} tracks from your library."


# -- playlist management (destructive tools use a two-step confirm protocol) ----------


def update_playlist(
    playlist: str,
    name: str | None = None,
    description: str | None = None,
    public: bool | None = None,
) -> str:
    """Change a playlist's name, description, or visibility. Only provided
    fields are changed."""
    get_service().update_playlist(playlist, name, description, public)
    return "Playlist updated."


def delete_playlist(playlist: str, confirm: bool = False) -> str:
    """Delete (unfollow) a playlist. DESTRUCTIVE: call once without confirm to
    get a preview, then again with confirm=true to proceed."""
    service = get_service()
    target = service.get_playlist(playlist)
    if not confirm:
        return (
            f"CONFIRMATION REQUIRED: this will delete the playlist {target.name!r} "
            f"({target.total_tracks} tracks). No changes were made. "
            "Call delete_playlist again with confirm=true to proceed. "
            "(Spotify keeps deleted playlists recoverable for 90 days.)"
        )
    name = service.delete_playlist(playlist)
    return f"Deleted playlist {name!r}."


def shuffle_playlist(playlist: str, confirm: bool = False, force: bool = False) -> str:
    """Persistently shuffle a playlist's track order. DESTRUCTIVE to ordering:
    call once without confirm for a preview, then with confirm=true. A full
    recovery snapshot is written before any change. Playlists containing local
    tracks are refused unless force=true (those tracks would be lost)."""
    service = get_service()
    target = service.get_playlist(playlist)
    if not confirm:
        return (
            f"CONFIRMATION REQUIRED: this will permanently reorder all "
            f"{target.total_tracks} tracks of {target.name!r}. A recovery snapshot "
            "is written first. No changes were made. Call shuffle_playlist again "
            "with confirm=true to proceed."
        )
    count = service.shuffle_playlist(playlist, force=force)
    return f"Shuffled {count} tracks of {target.name!r}. Recovery snapshot removed after success."


ALL_TOOLS = [
    user_profile,
    currently_playing,
    playlists,
    playlist_items,
    search,
    create_playlist,
    add_to_playlist,
    remove_from_playlist,
    library_tracks,
    recent_history,
    playback_state,
    play,
    pause,
    skip_next,
    skip_previous,
    queue_add,
    set_volume,
    top_items,
    lookup,
    save_to_library,
    remove_from_library,
    update_playlist,
    delete_playlist,
    shuffle_playlist,
]
