import spotify_mcp.tools.definitions as tools
from spotify_mcp.models.schemas import Track


class StubService:
    def __init__(self, now=None):
        self.now = now
        self.search_args = None

    def currently_playing(self):
        return self.now

    def search(self, query, types, limit):
        self.search_args = (query, types, limit)
        return {"tracks": []}

    def recently_played(self, limit=20):
        return [{"played_at": "2026-07-11T00:00:00Z", "track": Track(id=None, uri="u", name="n")}]


def test_currently_playing_idle_returns_message(monkeypatch):
    # review #15: the 204 branch is real logic and was untested
    monkeypatch.setattr(tools, "get_service", lambda: StubService(now=None))
    assert tools.currently_playing() == "Nothing is playing."


def test_currently_playing_dumps_track_model(monkeypatch):
    now = {"is_playing": True, "progress_ms": 5, "track": Track(id=None, uri="u", name="Song")}
    monkeypatch.setattr(tools, "get_service", lambda: StubService(now=now))
    result = tools.currently_playing()
    assert isinstance(result, dict)
    assert result["track"]["name"] == "Song"  # dumped to plain dict at the boundary


def test_search_defaults_to_track_type(monkeypatch):
    stub = StubService()
    monkeypatch.setattr(tools, "get_service", lambda: stub)
    tools.search("query")
    assert stub.search_args == ("query", ("track",), 10)


class ConfirmStubService:
    """Records mutations; playlist metadata is canned."""

    def __init__(self):
        self.mutations = []

    def get_playlist(self, ref):
        from spotify_mcp.models.schemas import Playlist

        return Playlist(
            id="p" * 22, uri="spotify:playlist:" + "p" * 22, name="Mix", total_tracks=42
        )

    def delete_playlist(self, ref):
        self.mutations.append(("delete", ref))
        return "Mix"

    def shuffle_playlist(self, ref, force=False):
        self.mutations.append(("shuffle", ref, force))
        return 42


def test_delete_playlist_requires_confirmation(monkeypatch):
    stub = ConfirmStubService()
    monkeypatch.setattr(tools, "get_service", lambda: stub)
    message = tools.delete_playlist("p" * 22)
    assert "CONFIRMATION REQUIRED" in message
    assert "42 tracks" in message
    assert stub.mutations == []  # nothing happened without confirm


def test_delete_playlist_confirmed_executes(monkeypatch):
    stub = ConfirmStubService()
    monkeypatch.setattr(tools, "get_service", lambda: stub)
    assert "Deleted playlist 'Mix'" in tools.delete_playlist("p" * 22, confirm=True)
    assert stub.mutations == [("delete", "p" * 22)]


def test_shuffle_playlist_requires_confirmation(monkeypatch):
    stub = ConfirmStubService()
    monkeypatch.setattr(tools, "get_service", lambda: stub)
    message = tools.shuffle_playlist("p" * 22)
    assert "CONFIRMATION REQUIRED" in message
    assert stub.mutations == []


def test_shuffle_playlist_confirmed_passes_force_through(monkeypatch):
    stub = ConfirmStubService()
    monkeypatch.setattr(tools, "get_service", lambda: stub)
    assert "Shuffled 42 tracks" in tools.shuffle_playlist("p" * 22, confirm=True, force=True)
    assert stub.mutations == [("shuffle", "p" * 22, True)]


def test_top_items_rejects_unknown_kind(monkeypatch):
    monkeypatch.setattr(tools, "get_service", lambda: StubService())
    import pytest

    with pytest.raises(ValueError, match="tracks.*artists"):
        tools.top_items(kind="albums")


def test_recent_history_dumps_models(monkeypatch):
    monkeypatch.setattr(tools, "get_service", lambda: StubService())
    [item] = tools.recent_history()
    assert item["track"] == {
        "id": None,
        "uri": "u",
        "name": "n",
        "artists": [],
        "album": None,
        "duration_ms": 0,
        "is_local": False,
    }
