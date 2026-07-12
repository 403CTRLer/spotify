from collections.abc import Sequence
from typing import Any

import pytest

from spotify_mcp.exceptions.errors import ApiError
from spotify_mcp.models.schemas import Page, PlayedItem, Playlist, Track, User
from spotify_mcp.services.service import SpotifyService

ME = "m" * 22
PL_A = "a" * 22
PL_B = "b" * 22
PL_C = "c" * 22


def uri(n: int) -> str:
    return f"spotify:track:{n:022d}"


def pl_uri(playlist_id: str) -> str:
    return f"spotify:playlist:{playlist_id}"


class FakeRepo:
    """In-memory SpotifyRepository recording every mutating call in order.

    reorder_playlist applies real list moves and enforces optimistic
    concurrency: a stale snapshot_id raises, so the service only passes if it
    threads the token correctly call-to-call.
    """

    def __init__(self):
        self.playlists: dict[str, Playlist] = {}
        self.playlist_uris: dict[str, list[str]] = {}
        self.saved_ids: list[str] = []
        self.calls: list[tuple[str, Any]] = []
        self.reorder_count = 0
        self.reorder_fail_at: int | None = None  # raise on the Nth reorder call
        self._snapshots: dict[str, str] = {}

    def add_playlist(self, playlist_id: str, name: str, owner_id: str = ME, uris=()):
        self.playlists[playlist_id] = Playlist(
            id=playlist_id,
            uri=pl_uri(playlist_id),
            name=name,
            owner_id=owner_id,
            total_tracks=len(uris),
        )
        self.playlist_uris[playlist_id] = list(uris)

    # -- protocol ------------------------------------------------------------

    def me(self) -> User:
        return User(id=ME, display_name="Tester")

    def my_playlists(self, limit: int = 50, offset: int = 0) -> Page[Playlist]:
        items = list(self.playlists.values())[offset : offset + limit]
        return {"total": len(self.playlists), "offset": offset, "items": items}

    def all_my_playlists(self) -> list[Playlist]:
        return list(self.playlists.values())

    def get_playlist(self, playlist_id: str) -> Playlist:
        return self.playlists[playlist_id]

    def playlist_snapshot_id(self, playlist_id: str) -> str:
        self.calls.append(("snapshot_id", playlist_id))
        return self._snapshots.setdefault(playlist_id, "snap-0")

    def playlist_items(self, playlist_id: str, limit: int = 100, offset: int = 0) -> Page[Track]:
        return {"total": len(self.playlist_uris[playlist_id]), "offset": offset, "items": []}

    def all_playlist_uris(self, playlist_id: str) -> list[str]:
        return [u for u in self.playlist_uris[playlist_id] if not u.startswith("spotify:local:")]

    def search(self, query: str, types: Sequence[str], limit: int = 10) -> dict[str, Any]:
        return {}

    def create_playlist(self, name: str, description: str = "", public: bool = False) -> Playlist:
        raise NotImplementedError

    def add_items(self, playlist_id: str, uris: Sequence[str]) -> int:
        self.calls.append(("add", playlist_id))
        self.playlist_uris.setdefault(playlist_id, []).extend(uris)
        return len(uris)

    def remove_items(self, playlist_id: str, uris: Sequence[str]) -> int:
        self.calls.append(("remove", playlist_id))
        doomed = set(uris)
        existing = self.playlist_uris.setdefault(playlist_id, [])
        existing[:] = [u for u in existing if u not in doomed]
        return len(uris)

    def reorder_playlist(
        self, playlist_id: str, range_start: int, insert_before: int, snapshot_id: str
    ) -> str:
        if snapshot_id != self._snapshots.get(playlist_id, "snap-0"):
            raise ApiError("stale snapshot_id", status=400)
        if self.reorder_fail_at is not None and self.reorder_count >= self.reorder_fail_at:
            raise ApiError("boom mid-shuffle", status=500)
        items = self.playlist_uris[playlist_id]
        items.insert(insert_before, items.pop(range_start))
        self.reorder_count += 1
        self.calls.append(("reorder", (range_start, insert_before)))
        new_snapshot = f"snap-{self.reorder_count}"
        self._snapshots[playlist_id] = new_snapshot
        return new_snapshot

    def saved_tracks(self, limit: int = 50, offset: int = 0) -> Page[Track]:
        return {"total": len(self.saved_ids), "offset": offset, "items": []}

    def all_saved_ids(self) -> list[str]:
        return list(self.saved_ids)

    def save_tracks(self, track_ids: Sequence[str]) -> int:
        self.calls.append(("save_tracks", list(track_ids)))
        self.saved_ids.extend(track_ids)
        return len(track_ids)

    def remove_saved(self, track_ids: Sequence[str]) -> int:
        self.calls.append(("remove_saved", len(track_ids)))
        doomed = set(track_ids)
        self.saved_ids = [i for i in self.saved_ids if i not in doomed]
        return len(track_ids)

    def recently_played(self, limit: int = 20) -> list[PlayedItem]:
        return []

    def playback_state(self) -> dict[str, Any] | None:
        return None

    def devices(self) -> list[dict[str, Any]]:
        return []

    def start_playback(
        self,
        device_id: str | None = None,
        context_uri: str | None = None,
        uris: Sequence[str] | None = None,
    ) -> None:
        self.calls.append(("play", (device_id, context_uri, tuple(uris or ()))))

    def pause_playback(self, device_id: str | None = None) -> None:
        self.calls.append(("pause", device_id))

    def skip_next(self) -> None:
        self.calls.append(("next", None))

    def skip_previous(self) -> None:
        self.calls.append(("previous", None))

    def add_to_queue(self, uri: str) -> None:
        self.calls.append(("queue", uri))

    def set_volume(self, percent: int) -> None:
        self.calls.append(("volume", percent))

    def top_tracks(
        self, limit: int = 20, offset: int = 0, time_range: str = "medium_term"
    ) -> Page[Track]:
        self.calls.append(("top_tracks", time_range))
        return {"total": 0, "offset": offset, "items": []}

    def top_artists(
        self, limit: int = 20, offset: int = 0, time_range: str = "medium_term"
    ) -> Page[dict[str, Any]]:
        self.calls.append(("top_artists", time_range))
        return {"total": 0, "offset": offset, "items": []}

    def get_track(self, track_id: str) -> Track:
        return Track(id=track_id, uri=f"spotify:track:{track_id}", name="T")

    def get_album(self, album_id: str) -> dict[str, Any]:
        return {"id": album_id, "name": "Al"}

    def get_artist(self, artist_id: str) -> dict[str, Any]:
        return {"id": artist_id, "name": "Ar"}

    def update_playlist(self, playlist_id: str, changes: dict[str, Any]) -> None:
        self.calls.append(("update_playlist", (playlist_id, changes)))

    def unfollow_playlist(self, playlist_id: str) -> None:
        self.calls.append(("unfollow", playlist_id))
        self.playlists.pop(playlist_id, None)


@pytest.fixture
def repo():
    return FakeRepo()


@pytest.fixture
def service(repo):
    return SpotifyService(repo)


# -- shuffle: lossless in-place reorder ------------------------------------------


def test_shuffle_keeps_every_item_including_local_tracks(service, repo):
    original = [uri(i) for i in range(10)]
    original.insert(3, "spotify:local:me:album:song:180")  # the headline regression
    repo.add_playlist(PL_A, "Mix", uris=original)
    assert service.shuffle_playlist(PL_A) == 11
    assert sorted(repo.playlist_uris[PL_A]) == sorted(original)
    assert repo.reorder_count <= 10  # at most n-1 moves


def test_shuffle_is_deterministic_under_forced_choices(service, repo, monkeypatch):
    # randint always picking the last index turns Fisher-Yates into a reversal
    import spotify_mcp.services.service as service_module

    original = [uri(1), uri(2), uri(3)]
    repo.add_playlist(PL_A, "Mix", uris=original)
    monkeypatch.setattr(service_module.random, "randint", lambda a, b: b)
    service.shuffle_playlist(PL_A)
    assert repo.playlist_uris[PL_A] == list(reversed(original))


def test_shuffle_threads_snapshot_id_between_calls(service, repo, monkeypatch):
    # FakeRepo raises on any stale snapshot_id, so success proves threading
    import spotify_mcp.services.service as service_module

    repo.add_playlist(PL_A, "Mix", uris=[uri(i) for i in range(6)])
    monkeypatch.setattr(service_module.random, "randint", lambda a, b: b)
    service.shuffle_playlist(PL_A)
    assert repo.reorder_count == 5


def test_shuffle_mid_run_failure_loses_nothing(service, repo, monkeypatch):
    import spotify_mcp.services.service as service_module

    original = [uri(i) for i in range(8)]
    repo.add_playlist(PL_A, "Mix", uris=original)
    monkeypatch.setattr(service_module.random, "randint", lambda a, b: b)
    repo.reorder_fail_at = 3
    with pytest.raises(ApiError, match="mid-shuffle"):
        service.shuffle_playlist(PL_A)
    assert sorted(repo.playlist_uris[PL_A]) == sorted(original)  # complete, just partial order


def test_shuffle_small_playlists_are_noops(service, repo):
    repo.add_playlist(PL_A, "Empty")
    repo.add_playlist(PL_B, "Single", uris=[uri(1)])
    assert service.shuffle_playlist(PL_A) == 0
    assert service.shuffle_playlist(PL_B) == 0
    assert repo.calls == []  # no snapshot fetch, no reorders


# -- mix: additive-only, playlist/track URL+URI sources ----------------------------


def test_mix_dedupes_and_reports_duplicates(service, repo):
    repo.add_playlist(PL_A, "Src1", uris=[uri(1), uri(2)])
    repo.add_playlist(PL_B, "Src2", uris=[uri(2), uri(3)])
    repo.add_playlist(PL_C, "Target")
    added, dupes = service.mix_playlists([pl_uri(PL_A), pl_uri(PL_B)], pl_uri(PL_C))
    assert (added, dupes) == (3, 1)
    assert sorted(repo.playlist_uris[PL_C]) == [uri(1), uri(2), uri(3)]


def test_mix_never_removes_from_target(service, repo):
    repo.add_playlist(PL_A, "Src", uris=[uri(1), uri(2)])
    repo.add_playlist(PL_C, "Target", uris=[uri(1)])
    added, dupes = service.mix_playlists([pl_uri(PL_A)], pl_uri(PL_C))
    assert ("remove", PL_C) not in repo.calls
    assert repo.playlist_uris[PL_C] == [uri(1), uri(2)]
    assert (added, dupes) == (1, 1)


def test_mix_accepts_track_sources(service, repo):
    repo.add_playlist(PL_C, "Target")
    added, _ = service.mix_playlists([uri(7)], pl_uri(PL_C))
    assert added == 1
    assert repo.playlist_uris[PL_C] == [uri(7)]


def test_mix_rejects_bare_and_album_sources(service, repo):
    repo.add_playlist(PL_C, "Target")
    with pytest.raises(ValueError):  # bare IDs are ambiguous for mix sources
        service.mix_playlists(["d" * 22], pl_uri(PL_C))
    with pytest.raises(ValueError, match="playlists or tracks"):
        service.mix_playlists([f"spotify:album:{'d' * 22}"], pl_uri(PL_C))


# -- saved tracks ----------------------------------------------------------------


def test_saved_to_playlist_converts_ids_to_uris(service, repo):
    repo.saved_ids = [f"{i:022d}" for i in range(3)]
    repo.add_playlist(PL_A, "Liked Dump")
    assert service.saved_to_playlist(PL_A) == 3
    assert repo.playlist_uris[PL_A] == [uri(0), uri(1), uri(2)]


def test_clear_saved_tracks_removes_everything(service, repo):
    repo.saved_ids = [f"{i:022d}" for i in range(5)]
    assert service.clear_saved_tracks() == 5
    assert repo.saved_ids == []


# -- ref validation at service boundaries -----------------------------------------


def test_playlist_items_rejects_track_ref(service):
    with pytest.raises(ValueError, match="playlist"):
        service.playlist_items(f"spotify:track:{'t' * 22}")


def test_add_to_playlist_parses_track_urls(service, repo):
    repo.add_playlist(PL_A, "Target")
    track = "t" * 22
    count = service.add_to_playlist(PL_A, [f"https://open.spotify.com/track/{track}?si=1"])
    assert count == 1
    assert repo.playlist_uris[PL_A] == [f"spotify:track:{track}"]


def test_me_is_cached(service, repo):
    assert service.me().id == ME
    assert service.me() is service.me()


# -- playback ---------------------------------------------------------------------


def test_play_track_ref_uses_uris(service, repo):
    track = "t" * 22
    msg = service.play(f"https://open.spotify.com/track/{track}")
    assert repo.calls == [("play", (None, None, (f"spotify:track:{track}",)))]
    assert "track" in msg


def test_play_playlist_ref_uses_context(service, repo):
    msg = service.play(f"spotify:playlist:{PL_A}", device_id="d1")
    assert repo.calls == [("play", ("d1", f"spotify:playlist:{PL_A}", ()))]
    assert "playlist" in msg


def test_play_without_ref_resumes(service, repo):
    assert service.play() == "Resumed playback."
    assert repo.calls == [("play", (None, None, ()))]


def test_volume_validation(service, repo):
    with pytest.raises(ValueError, match="0-100"):
        service.set_volume(150)
    assert repo.calls == []
    service.set_volume(30)
    assert repo.calls == [("volume", 30)]


def test_queue_add_parses_track_ref(service, repo):
    track = "t" * 22
    service.queue_add(f"https://open.spotify.com/track/{track}?si=x")
    assert repo.calls == [("queue", f"spotify:track:{track}")]


# -- personalization / lookup -------------------------------------------------------


def test_time_range_aliases_and_validation(service, repo):
    service.top_tracks("short")
    service.top_artists("long_term")
    assert repo.calls == [("top_tracks", "short_term"), ("top_artists", "long_term")]
    with pytest.raises(ValueError, match="time_range"):
        service.top_tracks("yearly")


def test_lookup_dispatches_by_ref_type(service, repo):
    track = "t" * 22
    assert service.lookup(f"spotify:track:{track}")["type"] == "track"
    assert service.lookup(f"spotify:album:{track}")["type"] == "album"
    assert service.lookup(f"spotify:artist:{track}")["type"] == "artist"
    repo.add_playlist(PL_A, "P")
    assert service.lookup(pl_uri(PL_A))["type"] == "playlist"
    with pytest.raises(ValueError):  # bare IDs are ambiguous for lookup
        service.lookup(track)


# -- library save/remove -------------------------------------------------------------


def test_save_library_tracks_parses_refs(service, repo):
    track = "t" * 22
    assert service.save_library_tracks([f"https://open.spotify.com/track/{track}"]) == 1
    assert repo.calls == [("save_tracks", [track])]


# -- playlist management --------------------------------------------------------------


def test_update_playlist_sends_only_provided_fields(service, repo):
    repo.add_playlist(PL_A, "Old")
    service.update_playlist(PL_A, name="New", public=False)
    assert repo.calls == [("update_playlist", (PL_A, {"name": "New", "public": False}))]


def test_update_playlist_with_no_changes_raises(service, repo):
    with pytest.raises(ValueError, match="Nothing to update"):
        service.update_playlist(PL_A)
    assert repo.calls == []


def test_delete_playlist_unfollows_and_returns_name(service, repo):
    repo.add_playlist(PL_A, "Doomed")
    assert service.delete_playlist(PL_A) == "Doomed"
    assert ("unfollow", PL_A) in repo.calls
    assert PL_A not in repo.playlists
