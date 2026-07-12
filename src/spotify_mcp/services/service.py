import logging
import random
from collections.abc import Sequence
from typing import Any

from spotify_mcp.models.schemas import Page, PlayedItem, Playlist, Track, User
from spotify_mcp.repository.spotify import SpotifyRepository
from spotify_mcp.utils.links import parse_ref, to_uri

log = logging.getLogger(__name__)


class SpotifyService:
    """All business logic. Provider-agnostic via SpotifyRepository.

    Never prints or prompts - stdout is the MCP wire; interaction is a CLI concern.
    """

    def __init__(self, repo: SpotifyRepository) -> None:
        self._repo = repo
        self._me: User | None = None

    # -- reads ----------------------------------------------------------------

    def me(self) -> User:
        if self._me is None:
            self._me = self._repo.me()
        return self._me

    def my_playlists(self, limit: int = 50, offset: int = 0) -> Page[Playlist]:
        return self._repo.my_playlists(limit, offset)

    def all_playlists(self) -> list[Playlist]:
        return self._repo.all_my_playlists()

    def playlist_items(self, ref: str, limit: int = 100, offset: int = 0) -> Page[Track]:
        _, playlist_id = parse_ref(ref, "playlist")
        return self._repo.playlist_items(playlist_id, limit, offset)

    def search(
        self, query: str, types: Sequence[str] = ("track",), limit: int = 10
    ) -> dict[str, Any]:
        return self._repo.search(query, types, limit)

    def saved_tracks(self, limit: int = 50, offset: int = 0) -> Page[Track]:
        return self._repo.saved_tracks(limit, offset)

    def recently_played(self, limit: int = 20) -> list[PlayedItem]:
        return self._repo.recently_played(limit)

    # -- playback (control requires Spotify Premium) ----------------------------

    def playback(self) -> dict[str, Any]:
        """Current playback state plus available devices."""
        return {"state": self._repo.playback_state(), "devices": self._repo.devices()}

    def play(self, ref: str | None = None, device_id: str | None = None) -> str:
        """Resume playback, or play a track/album/playlist/artist reference."""
        if not ref:
            self._repo.start_playback(device_id=device_id)
            return "Resumed playback."
        kind, spotify_id = parse_ref(ref, bare_type="track")
        uri = to_uri(kind, spotify_id)
        if kind == "track":
            self._repo.start_playback(device_id=device_id, uris=[uri])
        else:  # album/playlist/artist play as a context
            self._repo.start_playback(device_id=device_id, context_uri=uri)
        return f"Playing {kind} {spotify_id}."

    def pause(self, device_id: str | None = None) -> None:
        self._repo.pause_playback(device_id)

    def skip_next(self) -> None:
        self._repo.skip_next()

    def skip_previous(self) -> None:
        self._repo.skip_previous()

    def queue_add(self, track_ref: str) -> None:
        self._repo.add_to_queue(to_uri(*parse_ref(track_ref, "track")))

    def set_volume(self, percent: int) -> None:
        if not 0 <= percent <= 100:
            raise ValueError(f"Volume must be 0-100, got {percent}")
        self._repo.set_volume(percent)

    # -- personalization and catalog lookup --------------------------------------

    _TIME_RANGES = {"short": "short_term", "medium": "medium_term", "long": "long_term"}

    def _time_range(self, value: str) -> str:
        normalized = self._TIME_RANGES.get(value, value)
        if normalized not in self._TIME_RANGES.values():
            raise ValueError(f"time_range must be one of {sorted(self._TIME_RANGES)}")
        return normalized

    def top_tracks(
        self, time_range: str = "medium", limit: int = 20, offset: int = 0
    ) -> Page[Track]:
        return self._repo.top_tracks(limit, offset, self._time_range(time_range))

    def top_artists(
        self, time_range: str = "medium", limit: int = 20, offset: int = 0
    ) -> Page[dict[str, Any]]:
        return self._repo.top_artists(limit, offset, self._time_range(time_range))

    def get_playlist(self, ref: str) -> Playlist:
        _, playlist_id = parse_ref(ref, "playlist")
        return self._repo.get_playlist(playlist_id)

    def lookup(self, ref: str) -> dict[str, Any]:
        """Metadata for a track/album/artist/playlist URL or URI."""
        kind, spotify_id = parse_ref(ref)
        if kind == "track":
            return {"type": "track", **self._repo.get_track(spotify_id).model_dump()}
        if kind == "album":
            return {"type": "album", **self._repo.get_album(spotify_id)}
        if kind == "artist":
            return {"type": "artist", **self._repo.get_artist(spotify_id)}
        return {"type": "playlist", **self._repo.get_playlist(spotify_id).model_dump()}

    # -- library -----------------------------------------------------------------

    def save_library_tracks(self, track_refs: Sequence[str]) -> int:
        return self._repo.save_tracks([parse_ref(r, "track")[1] for r in track_refs])

    def remove_library_tracks(self, track_refs: Sequence[str]) -> int:
        return self._repo.remove_saved([parse_ref(r, "track")[1] for r in track_refs])

    # -- writes ---------------------------------------------------------------

    def create_playlist(self, name: str, description: str = "", public: bool = False) -> Playlist:
        return self._repo.create_playlist(name, description, public)

    def add_to_playlist(self, playlist_ref: str, track_refs: Sequence[str]) -> int:
        _, playlist_id = parse_ref(playlist_ref, "playlist")
        uris = [to_uri(*parse_ref(ref, "track")) for ref in track_refs]
        return self._repo.add_items(playlist_id, uris)

    def remove_from_playlist(self, playlist_ref: str, track_refs: Sequence[str]) -> int:
        _, playlist_id = parse_ref(playlist_ref, "playlist")
        uris = [to_uri(*parse_ref(ref, "track")) for ref in track_refs]
        return self._repo.remove_items(playlist_id, uris)

    def update_playlist(
        self,
        ref: str,
        name: str | None = None,
        description: str | None = None,
        public: bool | None = None,
    ) -> None:
        changes: dict[str, Any] = {
            key: value
            for key, value in {"name": name, "description": description, "public": public}.items()
            if value is not None
        }
        if not changes:
            raise ValueError("Nothing to update: provide name, description, or public")
        _, playlist_id = parse_ref(ref, "playlist")
        self._repo.update_playlist(playlist_id, changes)

    def delete_playlist(self, ref: str) -> str:
        """Unfollow (= delete, for owned playlists). Returns the playlist name.

        Spotify keeps unfollowed playlists recoverable for 90 days via their
        account page, so this is softer than it sounds - still confirm-gated."""
        _, playlist_id = parse_ref(ref, "playlist")
        name = self._repo.get_playlist(playlist_id).name
        self._repo.unfollow_playlist(playlist_id)
        return name

    # -- composite workflows -------------------------------------------------------

    def collect_track_uris(self, ref: str) -> list[str]:
        """Track URIs from a playlist or track reference (URL/URI)."""
        kind, spotify_id = parse_ref(ref)
        if kind == "track":
            return [to_uri("track", spotify_id)]
        if kind == "playlist":
            return self._repo.all_playlist_uris(spotify_id)
        raise ValueError(f"Mix sources must be playlists or tracks, got a {kind}: {ref!r}")

    def mix_playlists(self, sources: Sequence[str], target_ref: str) -> tuple[int, int]:
        """Merge sources into target additively. Tracks already in the target stay
        where they are; only new tracks are appended (shuffled). Never removes
        anything, so there is no partial-failure data-loss window.
        Returns (added, duplicates)."""
        collected: list[str] = []
        for source in sources:
            collected.extend(self.collect_track_uris(source))
        unique = list(dict.fromkeys(collected))
        _, target_id = parse_ref(target_ref, "playlist")
        existing = set(self._repo.all_playlist_uris(target_id))
        to_add = [u for u in unique if u not in existing]
        random.shuffle(to_add)
        self._repo.add_items(target_id, to_add)
        return len(to_add), len(collected) - len(to_add)

    def shuffle_playlist(self, ref: str) -> int:
        """Shuffle a playlist by reordering items IN PLACE (Fisher-Yates via
        the atomic reorder operation). Nothing is ever removed or re-added, so
        every item - including local tracks - survives by construction; a
        mid-run failure leaves the playlist partially shuffled but complete.

        Costs ~one API call per track; slow on large playlists under
        development-mode rate limits, but lossless and compliant."""
        # TODO: order by track similarity instead of pure random shuffling
        _, playlist_id = parse_ref(ref, "playlist")
        total = self._repo.get_playlist(playlist_id).total_tracks
        if total < 2:
            return 0
        snapshot_id = self._repo.playlist_snapshot_id(playlist_id)
        for i in range(total - 1):
            j = random.randint(i, total - 1)
            if j != i:  # move the chosen item into slot i; slots < i are final
                snapshot_id = self._repo.reorder_playlist(playlist_id, j, i, snapshot_id)
        return total

    def saved_to_playlist(self, target_ref: str) -> int:
        """Add all liked songs to a playlist. Returns the number added."""
        _, target_id = parse_ref(target_ref, "playlist")
        uris = [to_uri("track", track_id) for track_id in self._repo.all_saved_ids()]
        return self._repo.add_items(target_id, uris)

    def clear_saved_tracks(self) -> int:
        """Remove ALL liked songs. Destructive - confirmation belongs to the caller."""
        return self._repo.remove_saved(self._repo.all_saved_ids())
