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
]
