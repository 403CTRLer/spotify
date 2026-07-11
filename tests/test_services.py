from collections.abc import Sequence
from typing import Any

import pytest

from spotify_mcp.exceptions.errors import ApiError, LocalTracksError
from spotify_mcp.models.schemas import NowPlaying, Page, PlayedItem, Playlist, Track, User
from spotify_mcp.services.service import SpotifyService

ME = "m" * 22
PL_A = "a" * 22
PL_B = "b" * 22
PL_C = "c" * 22


def uri(n: int) -> str:
    return f"spotify:track:{n:022d}"


class FakeRepo:
    """In-memory SpotifyRepository recording every mutating call in order."""

    def __init__(self):
        self.playlists: dict[str, Playlist] = {}
        self.playlist_uris: dict[str, list[str]] = {}
        self.playlist_skipped: dict[str, list[str]] = {}  # local/unavailable per playlist
        self.saved_ids: list[str] = []
        self.calls: list[tuple[str, Any]] = []
        self.on_replace = None  # optional hook: (playlist_id, uris) -> None

    def add_playlist(self, playlist_id: str, name: str, owner_id: str = ME, uris=()):
        self.playlists[playlist_id] = Playlist(
            id=playlist_id, uri=f"spotify:playlist:{playlist_id}", name=name, owner_id=owner_id
        )
        self.playlist_uris[playlist_id] = list(uris)

    # -- protocol ------------------------------------------------------------

    def me(self) -> User:
        return User(id=ME, display_name="Tester")

    def currently_playing(self) -> NowPlaying | None:
        return None

    def my_playlists(self, limit: int = 50, offset: int = 0) -> Page[Playlist]:
        items = list(self.playlists.values())[offset : offset + limit]
        return {"total": len(self.playlists), "offset": offset, "items": items}

    def all_my_playlists(self) -> list[Playlist]:
        return list(self.playlists.values())

    def get_playlist(self, playlist_id: str) -> Playlist:
        return self.playlists[playlist_id]

    def playlist_items(self, playlist_id: str, limit: int = 100, offset: int = 0) -> Page[Track]:
        return {"total": len(self.playlist_uris[playlist_id]), "offset": offset, "items": []}

    def all_playlist_uris(self, playlist_id: str) -> tuple[list[str], list[str]]:
        return list(self.playlist_uris[playlist_id]), list(
            self.playlist_skipped.get(playlist_id, [])
        )

    def album_track_uris(self, album_id: str) -> list[str]:
        return []

    def search(self, query: str, types: Sequence[str], limit: int = 10) -> dict[str, Any]:
        return {}

    def create_playlist(self, name: str, description: str = "", public: bool = False) -> Playlist:
        raise NotImplementedError

    def add_items(self, playlist_id: str, uris: Sequence[str]) -> int:
        self.calls.append(("add", playlist_id))
        existing = self.playlist_uris.setdefault(playlist_id, [])
        existing.extend(uris)
        return len(uris)

    def remove_items(self, playlist_id: str, uris: Sequence[str]) -> int:
        self.calls.append(("remove", playlist_id))
        doomed = set(uris)
        existing = self.playlist_uris.setdefault(playlist_id, [])
        existing[:] = [u for u in existing if u not in doomed]
        return len(uris)

    def replace_items(self, playlist_id: str, uris: Sequence[str]) -> None:
        self.calls.append(("replace", playlist_id))
        if self.on_replace:
            self.on_replace(playlist_id, uris)
        self.playlist_uris[playlist_id] = list(uris)

    def saved_tracks(self, limit: int = 50, offset: int = 0) -> Page[Track]:
        return {"total": len(self.saved_ids), "offset": offset, "items": []}

    def all_saved_ids(self) -> list[str]:
        return list(self.saved_ids)

    def remove_saved(self, track_ids: Sequence[str]) -> int:
        self.calls.append(("remove_saved", len(track_ids)))
        doomed = set(track_ids)
        self.saved_ids = [i for i in self.saved_ids if i not in doomed]
        return len(track_ids)

    def recently_played(self, limit: int = 20) -> list[PlayedItem]:
        return []


@pytest.fixture
def repo():
    return FakeRepo()


@pytest.fixture
def service(repo, tmp_path):
    return SpotifyService(repo, recovery_dir=tmp_path / "recovery")


# -- shuffle: snapshot-before-mutation (legacy bug 4) --------------------------


def test_shuffle_snapshot_exists_before_mutation(service, repo, tmp_path):
    repo.add_playlist(PL_A, "Mix", uris=[uri(i) for i in range(5)])
    seen = {}

    def on_replace(playlist_id, uris):
        snapshots = list((tmp_path / "recovery").glob("*.json"))
        seen["snapshots_at_mutation"] = len(snapshots)

    repo.on_replace = on_replace
    assert service.shuffle_playlist(PL_A) == 5
    assert seen["snapshots_at_mutation"] == 1  # snapshot written BEFORE replace ran


def test_shuffle_success_removes_snapshot_and_keeps_tracks(service, repo, tmp_path):
    original = [uri(i) for i in range(150)]
    repo.add_playlist(PL_A, "Mix", uris=original)
    service.shuffle_playlist(PL_A)
    assert sorted(repo.playlist_uris[PL_A]) == sorted(original)  # same tracks, new order
    assert list((tmp_path / "recovery").glob("*.json")) == []


def test_shuffle_failure_keeps_snapshot_with_full_list(service, repo, tmp_path):
    original = [uri(i) for i in range(7)]
    repo.add_playlist(PL_A, "Mix", uris=original)

    def on_replace(playlist_id, uris):
        raise ApiError("boom", status=500)

    repo.on_replace = on_replace
    with pytest.raises(ApiError, match="saved at") as exc_info:
        service.shuffle_playlist(PL_A)

    snapshots = list((tmp_path / "recovery").glob("*.json"))
    assert len(snapshots) == 1
    assert str(snapshots[0]) in str(exc_info.value)
    import json

    data = json.loads(snapshots[0].read_text())
    assert sorted(data["uris"]) == sorted(original)  # FULL list, not just a failed chunk


def test_shuffle_empty_playlist_is_noop(service, repo):
    repo.add_playlist(PL_A, "Empty")
    assert service.shuffle_playlist(PL_A) == 0
    assert repo.calls == []


# -- shuffle: local/unavailable track guard (review #1) -------------------------


def test_shuffle_refuses_playlists_with_local_tracks(service, repo, tmp_path):
    repo.add_playlist(PL_A, "Mix", uris=[uri(1)])
    repo.playlist_skipped[PL_A] = ["spotify:local:me:album:song:180"]
    with pytest.raises(LocalTracksError, match="1 local/unavailable"):
        service.shuffle_playlist(PL_A)
    assert repo.calls == []  # no mutation happened
    assert not (tmp_path / "recovery").exists()  # and no stray snapshot


def test_shuffle_force_shuffles_streamable_and_records_skipped(service, repo, tmp_path):
    repo.add_playlist(PL_A, "Mix", uris=[uri(1), uri(2)])
    repo.playlist_skipped[PL_A] = ["spotify:local:me:album:song:180"]
    seen = {}

    def on_replace(playlist_id, uris):
        import json

        snapshot = next(iter((tmp_path / "recovery").glob("*.json")))
        seen["skipped"] = json.loads(snapshot.read_text())["skipped"]

    repo.on_replace = on_replace
    assert service.shuffle_playlist(PL_A, force=True) == 2
    assert seen["skipped"] == ["spotify:local:me:album:song:180"]


def test_shuffle_all_skips_playlists_with_local_tracks(service, repo):
    repo.add_playlist(PL_A, "Clean", uris=[uri(1)])
    repo.add_playlist(PL_B, "HasLocals", uris=[uri(2)])
    repo.playlist_skipped[PL_B] = ["spotify:local:x"]
    results = dict(service.shuffle_all_owned())
    assert results["Clean"] == "shuffled"
    assert results["HasLocals"].startswith("skipped")
    assert repo.playlist_uris[PL_B] == [uri(2)]  # untouched


# -- shuffle_all_owned: ignore-list logic (legacy bugs 1 + 2) -------------------


def test_empty_ignore_list_ignores_nothing(service, repo):
    repo.add_playlist(PL_A, "Alpha", uris=[uri(1)])
    repo.add_playlist(PL_B, "Beta", uris=[uri(2)])
    results = dict(service.shuffle_all_owned(ignore=[]))
    assert results == {"Alpha": "shuffled", "Beta": "shuffled"}


def test_blank_ignore_entries_are_dropped(service, repo):
    # legacy bug: input().split(",") on empty input produced [""] and ignored everything
    repo.add_playlist(PL_A, "Alpha", uris=[uri(1)])
    results = dict(service.shuffle_all_owned(ignore=["", "  "]))
    assert results == {"Alpha": "shuffled"}


def test_ignore_by_playlist_url(service, repo):
    repo.add_playlist(PL_A, "Alpha", uris=[uri(1)])
    repo.add_playlist(PL_B, "Beta", uris=[uri(2)])
    url = f"https://open.spotify.com/playlist/{PL_A}?si=x"
    results = dict(service.shuffle_all_owned(ignore=[url]))
    assert results == {"Alpha": "ignored", "Beta": "shuffled"}


def test_ignore_by_partial_name_case_insensitive(service, repo):
    repo.add_playlist(PL_A, "Chill Vibes", uris=[uri(1)])
    repo.add_playlist(PL_B, "Workout", uris=[uri(2)])
    results = dict(service.shuffle_all_owned(ignore=["chill"]))
    assert results == {"Chill Vibes": "ignored", "Workout": "shuffled"}


def test_non_owned_playlists_are_skipped(service, repo):
    repo.add_playlist(PL_A, "Mine", uris=[uri(1)])
    repo.add_playlist(PL_B, "Theirs", owner_id="someone-else", uris=[uri(2)])
    results = dict(service.shuffle_all_owned())
    assert results == {"Mine": "shuffled"}


# -- mix: additive-only, no data-loss window (review #2) ------------------------


def test_mix_dedupes_and_reports_duplicates(service, repo):
    repo.add_playlist(PL_A, "Src1", uris=[uri(1), uri(2)])
    repo.add_playlist(PL_B, "Src2", uris=[uri(2), uri(3)])
    repo.add_playlist(PL_C, "Target")
    added, dupes = service.mix_playlists([PL_A, PL_B], PL_C)
    assert (added, dupes) == (3, 1)
    assert sorted(repo.playlist_uris[PL_C]) == [uri(1), uri(2), uri(3)]


def test_mix_never_removes_from_target(service, repo):
    repo.add_playlist(PL_A, "Src", uris=[uri(1), uri(2)])
    repo.add_playlist(PL_C, "Target", uris=[uri(1)])
    added, dupes = service.mix_playlists([PL_A], PL_C)
    assert ("remove", PL_C) not in repo.calls  # additive only: no destructive step
    assert repo.playlist_uris[PL_C] == [uri(1), uri(2)]  # existing copy stays in place
    assert (added, dupes) == (1, 1)


def test_mix_with_nothing_new_is_a_noop_add(service, repo):
    repo.add_playlist(PL_A, "Src", uris=[uri(1)])
    repo.add_playlist(PL_C, "Target", uris=[uri(1)])
    added, dupes = service.mix_playlists([PL_A], PL_C)
    assert (added, dupes) == (0, 1)
    assert repo.playlist_uris[PL_C] == [uri(1)]


# -- restore (review #6) ---------------------------------------------------------


def test_restore_replaces_playlist_and_deletes_snapshot(service, repo, tmp_path):
    import json

    repo.add_playlist(PL_A, "Broken", uris=[uri(1)])  # failure state: subset of snapshot
    snapshot = tmp_path / "snap.json"
    snapshot.write_text(
        json.dumps(
            {
                "playlist_id": PL_A,
                "name": "Broken",
                "uris": [uri(1), uri(2)],
                "skipped": ["spotify:local:x"],
            }
        )
    )
    name, count, skipped = service.restore_snapshot(snapshot)
    assert (name, count) == ("Broken", 2)
    assert skipped == ["spotify:local:x"]
    assert repo.playlist_uris[PL_A] == [uri(1), uri(2)]
    assert not snapshot.exists()  # consumed on success


def test_restore_refuses_when_playlist_gained_tracks(service, repo, tmp_path):
    # restore semantics: replace-restore must not silently discard edits made
    # after the failure it is recovering from
    import json

    from spotify_mcp.exceptions.errors import RestoreConflictError

    repo.add_playlist(PL_A, "Edited", uris=[uri(1), uri(9)])  # uri(9) added post-failure
    snapshot = tmp_path / "snap.json"
    snapshot.write_text(
        json.dumps({"playlist_id": PL_A, "name": "Edited", "uris": [uri(1), uri(2)]})
    )
    with pytest.raises(RestoreConflictError, match="gained 1 track"):
        service.restore_snapshot(snapshot)
    assert repo.playlist_uris[PL_A] == [uri(1), uri(9)]  # untouched
    assert snapshot.exists()  # kept for a --force retry

    name, count, _ = service.restore_snapshot(snapshot, force=True)
    assert (name, count) == ("Edited", 2)
    assert repo.playlist_uris[PL_A] == [uri(1), uri(2)]


def test_restore_proceeds_when_playlist_is_subset_of_snapshot(service, repo, tmp_path):
    # a partially-written playlist (the normal failure state) restores without force
    import json

    repo.add_playlist(PL_A, "Partial", uris=[uri(1)])
    snapshot = tmp_path / "snap.json"
    snapshot.write_text(
        json.dumps({"playlist_id": PL_A, "name": "Partial", "uris": [uri(1), uri(2)]})
    )
    _, count, _ = service.restore_snapshot(snapshot)
    assert count == 2


def test_restore_rejects_malformed_snapshots(service, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    with pytest.raises(ValueError, match="Cannot read"):
        service.restore_snapshot(bad)

    wrong_shape = tmp_path / "wrong.json"
    wrong_shape.write_text('{"uris": "nope"}')
    with pytest.raises(ValueError, match="not a spotify-mcp recovery snapshot"):
        service.restore_snapshot(wrong_shape)
    assert wrong_shape.exists()  # never deleted on failure


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
