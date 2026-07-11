import json
import logging
import random
import time
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

from spotify_mcp.exceptions.errors import ApiError, LocalTracksError, RestoreConflictError
from spotify_mcp.models.schemas import NowPlaying, Page, PlayedItem, Playlist, Track, User
from spotify_mcp.repository.spotify import SpotifyRepository
from spotify_mcp.utils.links import parse_ref, to_uri

log = logging.getLogger(__name__)

DEFAULT_RECOVERY_DIR = Path.home() / ".spotify-mcp" / "recovery"


class SpotifyService:
    """All business logic. Provider-agnostic via SpotifyRepository.

    Never prints or prompts - stdout is the MCP wire; interaction is a CLI concern.
    """

    def __init__(self, repo: SpotifyRepository, recovery_dir: Path | None = None) -> None:
        self._repo = repo
        self._recovery_dir = recovery_dir or DEFAULT_RECOVERY_DIR
        self._me: User | None = None

    # -- reads ----------------------------------------------------------------

    def me(self) -> User:
        if self._me is None:
            self._me = self._repo.me()
        return self._me

    def currently_playing(self) -> NowPlaying | None:
        return self._repo.currently_playing()

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

    # -- legacy workflows -------------------------------------------------------

    def collect_track_uris(self, ref: str) -> list[str]:
        """Track URIs from a playlist, album, or track reference (bare IDs = playlists)."""
        kind, spotify_id = parse_ref(ref, bare_type="playlist")
        if kind == "track":
            return [to_uri("track", spotify_id)]
        if kind == "playlist":
            uris, _skipped = self._repo.all_playlist_uris(spotify_id)
            return uris
        if kind == "album":
            return self._repo.album_track_uris(spotify_id)
        raise ValueError(f"Cannot collect tracks from a {kind} reference: {ref!r}")

    def mix_playlists(self, sources: Sequence[str], target_ref: str) -> tuple[int, int]:
        """Merge sources into target additively. Tracks already in the target stay
        where they are; only new tracks are appended (shuffled). Never removes
        anything, so there is no partial-failure data-loss window (review #2).
        Returns (added, duplicates)."""
        collected: list[str] = []
        for source in sources:
            collected.extend(self.collect_track_uris(source))
        unique = list(dict.fromkeys(collected))
        _, target_id = parse_ref(target_ref, "playlist")
        existing, _skipped = self._repo.all_playlist_uris(target_id)
        existing_set = set(existing)
        to_add = [u for u in unique if u not in existing_set]
        random.shuffle(to_add)
        self._repo.add_items(target_id, to_add)
        return len(to_add), len(collected) - len(to_add)

    def shuffle_playlist(self, ref: str, force: bool = False) -> int:
        """Persistently shuffle a playlist. Snapshots the full track list to disk
        BEFORE any mutation; the snapshot is removed only after success.

        Refuses to run when the playlist holds local/unavailable tracks (the
        rewrite would permanently drop them) unless `force` is set."""
        _, playlist_id = parse_ref(ref, "playlist")
        playlist = self._repo.get_playlist(playlist_id)
        uris, skipped = self._repo.all_playlist_uris(playlist_id)
        if skipped and not force:
            raise LocalTracksError(
                f"{playlist.name!r} contains {len(skipped)} local/unavailable track(s) that a "
                "shuffle would permanently remove (the API cannot re-add them). "
                "Re-run with force to shuffle only the streamable tracks."
            )
        if not uris:
            return 0
        snapshot = self._write_snapshot(playlist, uris, skipped)
        random.shuffle(uris)
        try:
            self._repo.replace_items(playlist_id, uris)
        except Exception as exc:
            log.error(
                "Replace failed for %r; recovery snapshot kept at %s", playlist.name, snapshot
            )
            raise ApiError(
                f"Shuffle of {playlist.name!r} failed mid-write; "
                f"the full track list is saved at {snapshot}"
            ) from exc
        snapshot.unlink(missing_ok=True)
        return len(uris)

    def shuffle_all_owned(self, ignore: Sequence[str] = ()) -> Iterator[tuple[str, str]]:
        """Shuffle every playlist owned by the user, yielding (name, status).

        `ignore` entries may be playlist links/URIs/IDs or (partial) names.
        Empty/blank entries are dropped, so an empty list ignores nothing.
        """
        terms = [term.strip() for term in ignore if term and term.strip()]
        ignored_ids: set[str] = set()
        name_terms: list[str] = []
        for term in terms:
            try:
                ignored_ids.add(parse_ref(term, "playlist")[1])
            except ValueError:
                name_terms.append(term.lower())

        me_id = self.me().id
        for playlist in self._repo.all_my_playlists():
            if playlist.owner_id != me_id:
                continue
            name = playlist.name.lower()
            if playlist.id in ignored_ids or any(term in name for term in name_terms):
                yield playlist.name, "ignored"
                continue
            try:
                self.shuffle_playlist(playlist.id)
            except LocalTracksError:
                yield playlist.name, "skipped (contains local/unavailable tracks)"
                continue
            yield playlist.name, "shuffled"

    def saved_to_playlist(self, target_ref: str) -> int:
        """Add all liked songs to a playlist. Returns the number added."""
        _, target_id = parse_ref(target_ref, "playlist")
        uris = [to_uri("track", track_id) for track_id in self._repo.all_saved_ids()]
        return self._repo.add_items(target_id, uris)

    def restore_snapshot(self, path: Path | str, force: bool = False) -> tuple[str, int, list[str]]:
        """Replace a playlist's contents from a recovery snapshot, deleting the
        snapshot on success. Returns (name, restored_count, skipped_entries).

        Refuses when the playlist contains tracks that are not in the snapshot
        (evidence of edits made after the failure) unless `force` is set.
        `skipped_entries` are local/unavailable tracks the snapshot could not
        capture; they cannot be restored via the API."""
        snapshot_path = Path(path)
        try:
            data = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"Cannot read snapshot {snapshot_path}: {exc}") from exc
        playlist_id, uris = data.get("playlist_id"), data.get("uris")
        if not isinstance(playlist_id, str) or not isinstance(uris, list):
            raise ValueError(f"{snapshot_path} is not a spotify-mcp recovery snapshot")
        if not force:
            current, _ = self._repo.all_playlist_uris(playlist_id)
            foreign = [u for u in current if u not in set(uris)]
            if foreign:
                raise RestoreConflictError(
                    f"The playlist gained {len(foreign)} track(s) after this snapshot was "
                    "taken; restoring would remove them. Re-run with force to overwrite."
                )
        self._repo.replace_items(playlist_id, uris)
        snapshot_path.unlink(missing_ok=True)
        name = data.get("name") or playlist_id
        return name, len(uris), list(data.get("skipped") or [])

    def clear_saved_tracks(self) -> int:
        """Remove ALL liked songs. Destructive - confirmation belongs to the caller."""
        return self._repo.remove_saved(self._repo.all_saved_ids())

    # -- internals ---------------------------------------------------------------

    def _write_snapshot(
        self, playlist: Playlist, uris: list[str], skipped: list[str] | None = None
    ) -> Path:
        self._recovery_dir.mkdir(parents=True, exist_ok=True)
        path = self._recovery_dir / f"{playlist.id}-{int(time.time())}.json"
        path.write_text(
            json.dumps(
                {
                    "playlist_id": playlist.id,
                    "name": playlist.name,
                    "uris": uris,
                    "skipped": skipped or [],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return path
