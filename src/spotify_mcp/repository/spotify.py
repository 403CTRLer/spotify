from collections.abc import Sequence
from typing import Any, Protocol

from spotify_mcp.client.api_client import SpotifyApiClient
from spotify_mcp.models.schemas import Page, PlayedItem, Playlist, Track, User

PLAYLIST_CHUNK = 100  # Spotify limit for playlist item writes
SAVED_CHUNK = 50  # Spotify limit for saved-track writes


def _chunks(items: Sequence[str], size: int) -> list[Sequence[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _clamp(limit: int, cap: int) -> int:
    """Keep page sizes inside Spotify's per-endpoint maxima instead of letting
    the API 400 on caller-supplied values (review #13)."""
    return max(1, min(limit, cap))


def _device(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": data.get("id"),
        "name": data.get("name"),
        "type": data.get("type"),
        "is_active": bool(data.get("is_active")),
        "volume_percent": data.get("volume_percent"),
    }


def _artist(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": data.get("id"),
        "name": data.get("name"),
        "uri": data.get("uri"),
        "genres": data.get("genres") or [],
        "popularity": data.get("popularity"),
        "followers": (data.get("followers") or {}).get("total"),
    }


class SpotifyRepository(Protocol):
    """Provider-facing data access. Services depend on this, never on HTTP."""

    def me(self) -> User: ...
    def my_playlists(self, limit: int = 50, offset: int = 0) -> Page[Playlist]: ...
    def all_my_playlists(self) -> list[Playlist]: ...
    def get_playlist(self, playlist_id: str) -> Playlist: ...
    def playlist_snapshot_id(self, playlist_id: str) -> str: ...
    def playlist_items(
        self, playlist_id: str, limit: int = 100, offset: int = 0
    ) -> Page[Track]: ...
    def all_playlist_uris(self, playlist_id: str) -> list[str]: ...
    def search(self, query: str, types: Sequence[str], limit: int = 10) -> dict[str, Any]: ...
    def create_playlist(
        self, name: str, description: str = "", public: bool = False
    ) -> Playlist: ...
    def add_items(self, playlist_id: str, uris: Sequence[str]) -> int: ...
    def remove_items(self, playlist_id: str, uris: Sequence[str]) -> int: ...
    def reorder_playlist(
        self, playlist_id: str, range_start: int, insert_before: int, snapshot_id: str
    ) -> str: ...
    def saved_tracks(self, limit: int = 50, offset: int = 0) -> Page[Track]: ...
    def all_saved_ids(self) -> list[str]: ...
    def save_tracks(self, track_ids: Sequence[str]) -> int: ...
    def remove_saved(self, track_ids: Sequence[str]) -> int: ...
    def recently_played(self, limit: int = 20) -> list[PlayedItem]: ...
    # playback (control requires Spotify Premium; dict shapes documented in
    # docs/tool-reference.md - heterogeneous like search, per ADR 0003)
    def playback_state(self) -> dict[str, Any] | None: ...
    def devices(self) -> list[dict[str, Any]]: ...
    def start_playback(
        self,
        device_id: str | None = None,
        context_uri: str | None = None,
        uris: Sequence[str] | None = None,
    ) -> None: ...
    def pause_playback(self, device_id: str | None = None) -> None: ...
    def skip_next(self) -> None: ...
    def skip_previous(self) -> None: ...
    def add_to_queue(self, uri: str) -> None: ...
    def set_volume(self, percent: int) -> None: ...
    # personalization and catalog lookup
    def top_tracks(
        self, limit: int = 20, offset: int = 0, time_range: str = "medium_term"
    ) -> Page[Track]: ...
    def top_artists(
        self, limit: int = 20, offset: int = 0, time_range: str = "medium_term"
    ) -> Page[dict[str, Any]]: ...
    def get_track(self, track_id: str) -> Track: ...
    def get_album(self, album_id: str) -> dict[str, Any]: ...
    def get_artist(self, artist_id: str) -> dict[str, Any]: ...
    # playlist management
    def update_playlist(self, playlist_id: str, changes: dict[str, Any]) -> None: ...
    def unfollow_playlist(self, playlist_id: str) -> None: ...


class SpotifyApiRepository:
    """SpotifyRepository over the Web API: endpoints, chunking, null filtering, mapping."""

    def __init__(self, client: SpotifyApiClient) -> None:
        self._client = client

    def me(self) -> User:
        return User.model_validate(self._client.get("/me"))

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

    def playlist_snapshot_id(self, playlist_id: str) -> str:
        """Transient optimistic-concurrency token for write workflows; not part
        of the Playlist domain model."""
        data = self._client.get(f"/playlists/{playlist_id}", fields="snapshot_id") or {}
        return data.get("snapshot_id") or ""

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

    def all_playlist_uris(self, playlist_id: str) -> list[str]:
        """Streamable track URIs. Local/unavailable entries are excluded: the
        Web API cannot re-ADD them, so they are unusable for additive callers
        (in-place reorders never touch this method)."""
        uris: list[str] = []
        for item in self._client.paginate(f"/playlists/{playlist_id}/tracks", limit=100):
            track = Track.from_api((item or {}).get("track") or {})
            if track.uri and not track.is_local:
                uris.append(track.uri)
        return uris

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

    def reorder_playlist(
        self, playlist_id: str, range_start: int, insert_before: int, snapshot_id: str
    ) -> str:
        """Move one item in place (atomic reorder). Returns the new snapshot_id."""
        data = self._client.put(
            f"/playlists/{playlist_id}/tracks",
            json={
                "range_start": range_start,
                "insert_before": insert_before,
                "range_length": 1,
                "snapshot_id": snapshot_id,
            },
        )
        return (data or {}).get("snapshot_id") or snapshot_id

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

    def save_tracks(self, track_ids: Sequence[str]) -> int:
        for chunk in _chunks(track_ids, SAVED_CHUNK):
            self._client.put("/me/tracks", json={"ids": list(chunk)})
        return len(track_ids)

    def remove_saved(self, track_ids: Sequence[str]) -> int:
        for chunk in _chunks(track_ids, SAVED_CHUNK):
            self._client.delete("/me/tracks", json={"ids": list(chunk)})
        return len(track_ids)

    # -- playback -------------------------------------------------------------

    def playback_state(self) -> dict[str, Any] | None:
        data = self._client.get("/me/player")
        if not data:
            return None
        item = data.get("item")
        return {
            "is_playing": bool(data.get("is_playing")),
            "progress_ms": data.get("progress_ms"),
            "shuffle_state": data.get("shuffle_state"),
            "repeat_state": data.get("repeat_state"),
            "device": _device(data.get("device") or {}),
            "track": Track.from_api(item).model_dump() if item else None,
        }

    def devices(self) -> list[dict[str, Any]]:
        data = self._client.get("/me/player/devices") or {}
        return [_device(d) for d in data.get("devices") or [] if d]

    def start_playback(
        self,
        device_id: str | None = None,
        context_uri: str | None = None,
        uris: Sequence[str] | None = None,
    ) -> None:
        body: dict[str, Any] = {}
        if context_uri:
            body["context_uri"] = context_uri
        if uris:
            body["uris"] = list(uris)
        params: dict[str, Any] = {"device_id": device_id} if device_id else {}
        self._client.put("/me/player/play", json=body or None, **params)

    def pause_playback(self, device_id: str | None = None) -> None:
        params: dict[str, Any] = {"device_id": device_id} if device_id else {}
        self._client.put("/me/player/pause", **params)

    def skip_next(self) -> None:
        self._client.post("/me/player/next")

    def skip_previous(self) -> None:
        self._client.post("/me/player/previous")

    def add_to_queue(self, uri: str) -> None:
        self._client.post("/me/player/queue", uri=uri)

    def set_volume(self, percent: int) -> None:
        self._client.put("/me/player/volume", volume_percent=percent)

    # -- personalization and catalog lookup ------------------------------------

    def top_tracks(
        self, limit: int = 20, offset: int = 0, time_range: str = "medium_term"
    ) -> Page[Track]:
        data = self._client.get(
            "/me/top/tracks", limit=_clamp(limit, 50), offset=offset, time_range=time_range
        )
        return {
            "total": data.get("total", 0),
            "offset": data.get("offset", offset),
            "items": [Track.from_api(i) for i in data.get("items") or [] if i],
        }

    def top_artists(
        self, limit: int = 20, offset: int = 0, time_range: str = "medium_term"
    ) -> Page[dict[str, Any]]:
        data = self._client.get(
            "/me/top/artists", limit=_clamp(limit, 50), offset=offset, time_range=time_range
        )
        return {
            "total": data.get("total", 0),
            "offset": data.get("offset", offset),
            "items": [_artist(i) for i in data.get("items") or [] if i],
        }

    def get_track(self, track_id: str) -> Track:
        return Track.from_api(self._client.get(f"/tracks/{track_id}"))

    def get_album(self, album_id: str) -> dict[str, Any]:
        data = self._client.get(f"/albums/{album_id}") or {}
        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "uri": data.get("uri"),
            "artists": [a.get("name") or "" for a in data.get("artists") or []],
            "release_date": data.get("release_date"),
            "total_tracks": data.get("total_tracks"),
            "label": data.get("label"),
        }

    def get_artist(self, artist_id: str) -> dict[str, Any]:
        return _artist(self._client.get(f"/artists/{artist_id}") or {})

    # -- playlist management ----------------------------------------------------

    def update_playlist(self, playlist_id: str, changes: dict[str, Any]) -> None:
        self._client.put(f"/playlists/{playlist_id}", json=changes)

    def unfollow_playlist(self, playlist_id: str) -> None:
        self._client.delete(f"/playlists/{playlist_id}/followers")

    def recently_played(self, limit: int = 20) -> list[PlayedItem]:
        data = self._client.get("/me/player/recently-played", limit=_clamp(limit, 50)) or {}
        return [
            {"played_at": item.get("played_at"), "track": Track.from_api(item["track"])}
            for item in data.get("items") or []
            if item and item.get("track")
        ]
