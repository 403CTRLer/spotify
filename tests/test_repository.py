import json

import httpx

from spotify_mcp.client.api_client import BASE_URL, SpotifyApiClient
from spotify_mcp.models.schemas import Playlist, Track
from spotify_mcp.repository.spotify import SpotifyApiRepository


class FakeAuth:
    def get_token(self) -> str:
        return "tok"

    def refresh_now(self) -> str:
        return "tok"


def make_repo(handler):
    http = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    return SpotifyApiRepository(SpotifyApiClient(FakeAuth(), http=http))


def recording_repo(responder):
    """Repo whose transport records (method, path, body) per request."""
    calls = []

    def handler(request):
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, request.url.path, body))
        return responder(request)

    return make_repo(handler), calls


def test_add_items_chunks_of_100():
    repo, calls = recording_repo(lambda request: httpx.Response(201, json={"snapshot_id": "s"}))
    uris = [f"spotify:track:{i:022d}" for i in range(250)]
    assert repo.add_items("pl", uris) == 250
    sizes = [len(body["uris"]) for method, path, body in calls]
    assert sizes == [100, 100, 50]
    assert all(method == "POST" and path == "/v1/playlists/pl/tracks" for method, path, _ in calls)


def test_replace_items_puts_head_then_posts_rest():
    repo, calls = recording_repo(lambda request: httpx.Response(200, json={"snapshot_id": "s"}))
    uris = [f"spotify:track:{i:022d}" for i in range(150)]
    repo.replace_items("pl", uris)
    assert [(m, len(b["uris"])) for m, _, b in calls] == [("PUT", 100), ("POST", 50)]


def test_remove_saved_chunks_of_50():
    repo, calls = recording_repo(lambda request: httpx.Response(200))
    assert repo.remove_saved([f"{i:022d}" for i in range(120)]) == 120
    assert [len(b["ids"]) for _, _, b in calls] == [50, 50, 20]
    assert all(m == "DELETE" and p == "/v1/me/tracks" for m, p, _ in calls)


def test_all_playlist_uris_skips_null_and_local_tracks():
    items = [
        {"track": {"id": "a" * 22, "uri": "spotify:track:" + "a" * 22}},
        {"track": None},  # removed/unavailable track
        None,  # defensive: null item
        {"track": {"id": None, "uri": "spotify:local:x", "is_local": True}},
        {"track": {"id": "b" * 22, "uri": "spotify:track:" + "b" * 22}},
    ]

    def handler(request):
        return httpx.Response(200, json={"items": items, "next": None})

    repo = make_repo(handler)
    uris, skipped = repo.all_playlist_uris("pl")
    assert uris == [
        "spotify:track:" + "a" * 22,
        "spotify:track:" + "b" * 22,
    ]
    # review #1: the skipped local/unavailable entries are surfaced, not silently dropped
    assert skipped == [
        "unavailable track (removed from catalog)",
        "unavailable track (removed from catalog)",
        "spotify:local:x",
    ]


def test_currently_playing_none_on_204():
    repo = make_repo(lambda request: httpx.Response(204))
    assert repo.currently_playing() is None


def test_currently_playing_returns_track_model():
    # review #7: envelopes carry live models until the tool boundary
    payload = {
        "is_playing": True,
        "progress_ms": 1234,
        "item": {"id": "x" * 22, "name": "Song", "uri": "spotify:track:" + "x" * 22},
    }
    repo = make_repo(lambda request: httpx.Response(200, json=payload))
    now = repo.currently_playing()
    assert now is not None
    assert now["is_playing"] is True
    assert isinstance(now["track"], Track)
    assert now["track"].name == "Song"


def test_search_filters_null_items():
    payload = {
        "tracks": {"items": [{"id": "t", "name": "Song", "uri": "u"}, None]},
        "artists": {"items": [None, {"id": "a", "name": "Artist", "uri": "au"}]},
    }
    repo = make_repo(lambda request: httpx.Response(200, json=payload))
    results = repo.search("q", types=("track", "artist"))
    assert [t["name"] for t in results["tracks"]] == ["Song"]
    assert [a["name"] for a in results["artists"]] == ["Artist"]


def test_track_from_api_tolerates_missing_fields():
    track = Track.from_api({"id": "x" * 22, "name": None, "artists": None, "album": None})
    assert track.uri == "spotify:track:" + "x" * 22
    assert track.artists == []
    assert not track.is_local


def test_playlist_from_api_tolerates_missing_fields():
    playlist = Playlist.from_api({"id": "p" * 22})
    assert playlist.uri == "spotify:playlist:" + "p" * 22
    assert playlist.owner_id == ""
    assert playlist.total_tracks == 0


def test_playlist_from_api_missing_id_raises_value_error():
    # review #4c: malformed API items raise ValueError (caught by the CLI), not KeyError
    import pytest

    with pytest.raises(ValueError, match="missing an id"):
        Playlist.from_api({"name": "ghost"})


def test_my_playlists_maps_page():
    payload = {
        "total": 2,
        "offset": 0,
        "items": [{"id": "p" * 22, "name": "Mix", "owner": {"id": "me"}}, None],
    }
    repo = make_repo(lambda request: httpx.Response(200, json=payload))
    page = repo.my_playlists()
    assert page["total"] == 2
    assert [p.name for p in page["items"]] == ["Mix"]
