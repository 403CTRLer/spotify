from collections.abc import Sequence
from typing import Any, Protocol

from spotify_mcp.client.api_client import SpotifyApiClient
from spotify_mcp.models.schemas import NowPlaying, Page, PlayedItem, Playlist, Track, User

PLAYLIST_CHUNK = 100  # Spotify limit for playlist item writes
SAVED_CHUNK = 50  # Spotify limit for saved-track writes


def _chunks(items: Sequence[str], size: int) -> list[Sequence[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _clamp(limit: int, cap: int) -> int:
    """Keep page sizes inside Spotify's per-endpoint maxima instead of letting
    the API 400 on caller-supplied values (review #13)."""
    return max(1, min(limit, cap))


class SpotifyRepository(Protocol):
    """Provider-facing data access. Services depend on this, never on HTTP."""

    def me(self) -> User: ...
    def currently_playing(self) -> NowPlaying | None: ...
    def my_playlists(self, limit: int = 50, offset: int = 0) -> Page[Playlist]: ...
    def all_my_playlists(self) -> list[Playlist]: ...
    def get_playlist(self, playlist_id: str) -> Playlist: ...
    def playlist_items(
        self, playlist_id: str, limit: int = 100, offset: int = 0
    ) -> Page[Track]: ...
    def all_playlist_uris(self, playlist_id: str) -> tuple[list[str], list[str]]: ...
    def album_track_uris(self, album_id: str) -> list[str]: ...
    def search(self, query: str, types: Sequence[str], limit: int = 10) -> dict[str, Any]: ...
    def create_playlist(
        self, name: str, description: str = "", public: bool = False
    ) -> Playlist: ...
    def add_items(self, playlist_id: str, uris: Sequence[str]) -> int: ...
    def remove_items(self, playlist_id: str, uris: Sequence[str]) -> int: ...
    def replace_items(self, playlist_id: str, uris: Sequence[str]) -> None: ...
    def saved_tracks(self, limit: int = 50, offset: int = 0) -> Page[Track]: ...
    def all_saved_ids(self) -> list[str]: ...
    def remove_saved(self, track_ids: Sequence[str]) -> int: ...
    def recently_played(self, limit: int = 20) -> list[PlayedItem]: ...


class SpotifyApiRepository:
    """SpotifyRepository over the Web API: endpoints, chunking, null filtering, mapping."""

    def __init__(self, client: SpotifyApiClient) -> None:
        self._client = client

    def me(self) -> User:
        return User.model_validate(self._client.get("/me"))

    def currently_playing(self) -> NowPlaying | None:
        data = self._client.get("/me/player/currently-playing")
        if not data or not data.get("item"):
            return None
        return {
            "is_playing": bool(data.get("is_playing")),
            "progress_ms": data.get("progress_ms"),
            "track": Track.from_api(data["item"]),
        }

    def my_playlists(self, limit: int = 50, offset: int = 0) -> Page[Playlist]:
        data = self._client.get("/me/playlists", limit=_clamp(limit, 50), offset=offset)
        return {
            "total": data.get("total", 0),
            "offset": data.get("offset", offset),
            "items": [Playlist.from_api(p) for p in data.get("items") or [] if p],
        }

    def all_my_playlists(self) -> list[Playlist]:
        return [Playlist.from_api(p) for p in self._client.paginate("/me/playlists", limit=50) if p]

    def get_playlist(self, playlist_id: str) -> Playlist:
        return Playlist.from_api(self._client.get(f"/playlists/{playlist_id}"))

    def playlist_items(self, playlist_id: str, limit: int = 100, offset: int = 0) -> Page[Track]:
        data = self._client.get(
            f"/playlists/{playlist_id}/tracks", limit=_clamp(limit, 100), offset=offset
        )
        return {
            "total": data.get("total", 0),
            "offset": data.get("offset", offset),
            "items": [
                Track.from_api(item["track"])
                for item in data.get("items") or []
                if item and item.get("track")
            ],
        }

    def all_playlist_uris(self, playlist_id: str) -> tuple[list[str], list[str]]:
        """Returns (streamable_uris, skipped) where skipped describes local and
        null/unavailable tracks the Web API cannot re-add."""
        uris: list[str] = []
        skipped: list[str] = []
        for item in self._client.paginate(f"/playlists/{playlist_id}/tracks", limit=100):
            raw = (item or {}).get("track")
            if not raw:
                skipped.append("unavailable track (removed from catalog)")
                continue
            track = Track.from_api(raw)
            if track.is_local or not track.uri:
                skipped.append(track.uri or track.name or "unknown local track")
                continue
            uris.append(track.uri)
        return uris, skipped

    def album_track_uris(self, album_id: str) -> list[str]:
        return [
            t["uri"]
            for t in self._client.paginate(f"/albums/{album_id}/tracks", limit=50)
            if t and t.get("uri")
        ]

    def search(self, query: str, types: Sequence[str], limit: int = 10) -> dict[str, Any]:
        data = (
            self._client.get("/search", q=query, type=",".join(types), limit=_clamp(limit, 50))
            or {}
        )
        results: dict[str, Any] = {}
        for key, page in data.items():
            items = [i for i in (page.get("items") or []) if i]  # search can contain nulls
            if key == "tracks":
                results[key] = [Track.from_api(i).model_dump() for i in items]
            elif key == "playlists":
                results[key] = [Playlist.from_api(i).model_dump() for i in items]
            else:
                results[key] = [
                    {"id": i.get("id"), "name": i.get("name"), "uri": i.get("uri")} for i in items
                ]
        return results

    def create_playlist(self, name: str, description: str = "", public: bool = False) -> Playlist:
        me_id = self.me().id
        data = self._client.post(
            f"/users/{me_id}/playlists",
            json={"name": name, "description": description, "public": public},
        )
        return Playlist.from_api(data)

    def add_items(self, playlist_id: str, uris: Sequence[str]) -> int:
        for chunk in _chunks(uris, PLAYLIST_CHUNK):
            self._client.post(f"/playlists/{playlist_id}/tracks", json={"uris": list(chunk)})
        return len(uris)

    def remove_items(self, playlist_id: str, uris: Sequence[str]) -> int:
        for chunk in _chunks(uris, PLAYLIST_CHUNK):
            self._client.delete(
                f"/playlists/{playlist_id}/tracks",
                json={"tracks": [{"uri": uri} for uri in chunk]},
            )
        return len(uris)

    def replace_items(self, playlist_id: str, uris: Sequence[str]) -> None:
        """Replace playlist contents: PUT the first chunk, append the rest."""
        head, rest = uris[:PLAYLIST_CHUNK], uris[PLAYLIST_CHUNK:]
        self._client.put(f"/playlists/{playlist_id}/tracks", json={"uris": list(head)})
        for chunk in _chunks(rest, PLAYLIST_CHUNK):
            self._client.post(f"/playlists/{playlist_id}/tracks", json={"uris": list(chunk)})

    def saved_tracks(self, limit: int = 50, offset: int = 0) -> Page[Track]:
        data = self._client.get("/me/tracks", limit=_clamp(limit, 50), offset=offset)
        return {
            "total": data.get("total", 0),
            "offset": data.get("offset", offset),
            "items": [
                Track.from_api(item["track"])
                for item in data.get("items") or []
                if item and item.get("track")
            ],
        }

    def all_saved_ids(self) -> list[str]:
        ids: list[str] = []
        for item in self._client.paginate("/me/tracks", limit=50):
            track = (item or {}).get("track") or {}
            if track.get("id"):
                ids.append(track["id"])
        return ids

    def remove_saved(self, track_ids: Sequence[str]) -> int:
        for chunk in _chunks(track_ids, SAVED_CHUNK):
            self._client.delete("/me/tracks", json={"ids": list(chunk)})
        return len(track_ids)

    def recently_played(self, limit: int = 20) -> list[PlayedItem]:
        data = self._client.get("/me/player/recently-played", limit=_clamp(limit, 50)) or {}
        return [
            {"played_at": item.get("played_at"), "track": Track.from_api(item["track"])}
            for item in data.get("items") or []
            if item and item.get("track")
        ]
