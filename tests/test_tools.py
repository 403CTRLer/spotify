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
