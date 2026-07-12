import json

import httpx

from spotify_mcp.api.client import BASE_URL, SpotifyApiClient
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


def test_reorder_playlist_sends_range_body_and_returns_new_snapshot():
    repo, calls = recording_repo(lambda request: httpx.Response(200, json={"snapshot_id": "s2"}))
    assert repo.reorder_playlist("pl", 7, 2, "s1") == "s2"
    assert calls == [
        (
            "PUT",
            "/v1/playlists/pl/tracks",
            {"range_start": 7, "insert_before": 2, "range_length": 1, "snapshot_id": "s1"},
        )
    ]


def test_playlist_snapshot_id_requests_only_that_field():
    seen = {}

    def handler(request):
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={"snapshot_id": "s9"})

    repo = make_repo(handler)
    assert repo.playlist_snapshot_id("pl") == "s9"
    assert seen == {"fields": "snapshot_id"}


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
    # additive callers get only re-addable URIs; local/null entries are excluded
    assert repo.all_playlist_uris("pl") == [
        "spotify:track:" + "a" * 22,
        "spotify:track:" + "b" * 22,
    ]


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


def test_limits_are_clamped_to_endpoint_maxima():
    # review #13: /me/tracks caps at 50; out-of-range limits must not 400
    seen = {}

    def handler(request):
        seen[request.url.path] = request.url.params.get("limit")
        return httpx.Response(200, json={"items": [], "total": 0, "offset": 0})

    repo = make_repo(handler)
    repo.saved_tracks(limit=100)
    repo.playlist_items("pl", limit=500)
    repo.my_playlists(limit=0)
    assert seen["/v1/me/tracks"] == "50"
    assert seen["/v1/playlists/pl/tracks"] == "100"
    assert seen["/v1/me/playlists"] == "1"


def test_playback_state_maps_device_and_track():
    payload = {
        "is_playing": True,
        "progress_ms": 42,
        "shuffle_state": False,
        "repeat_state": "off",
        "device": {
            "id": "d1",
            "name": "Desk",
            "type": "Computer",
            "is_active": True,
            "volume_percent": 60,
        },
        "item": {"id": "x" * 22, "name": "Song", "uri": "spotify:track:" + "x" * 22},
    }
    repo = make_repo(lambda request: httpx.Response(200, json=payload))
    state = repo.playback_state()
    assert state is not None
    assert state["device"]["name"] == "Desk"
    assert state["track"]["name"] == "Song"


def test_playback_state_none_when_idle():
    repo = make_repo(lambda request: httpx.Response(204))
    assert repo.playback_state() is None


def test_playback_commands_send_correct_requests():
    calls = []

    def handler(request):
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, request.url.path, dict(request.url.params), body))
        return httpx.Response(204)

    repo = make_repo(handler)
    repo.start_playback(uris=["spotify:track:" + "a" * 22])
    repo.start_playback(device_id="d1", context_uri="spotify:playlist:" + "p" * 22)
    repo.pause_playback()
    repo.skip_next()
    repo.skip_previous()
    repo.add_to_queue("spotify:track:" + "q" * 22)
    repo.set_volume(60)

    assert calls[0] == ("PUT", "/v1/me/player/play", {}, {"uris": ["spotify:track:" + "a" * 22]})
    assert calls[1] == (
        "PUT",
        "/v1/me/player/play",
        {"device_id": "d1"},
        {"context_uri": "spotify:playlist:" + "p" * 22},
    )
    assert calls[2] == ("PUT", "/v1/me/player/pause", {}, None)
    assert calls[3][:2] == ("POST", "/v1/me/player/next")
    assert calls[4][:2] == ("POST", "/v1/me/player/previous")
    assert calls[5] == ("POST", "/v1/me/player/queue", {"uri": "spotify:track:" + "q" * 22}, None)
    assert calls[6] == ("PUT", "/v1/me/player/volume", {"volume_percent": "60"}, None)


def test_devices_mapping():
    payload = {
        "devices": [
            {
                "id": "d1",
                "name": "Phone",
                "type": "Smartphone",
                "is_active": False,
                "volume_percent": 30,
            },
            None,
        ]
    }
    repo = make_repo(lambda request: httpx.Response(200, json=payload))
    assert repo.devices() == [
        {
            "id": "d1",
            "name": "Phone",
            "type": "Smartphone",
            "is_active": False,
            "volume_percent": 30,
        }
    ]


def test_top_tracks_sends_time_range_and_clamps_limit():
    seen = {}

    def handler(request):
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={"items": [], "total": 0, "offset": 0})

    repo = make_repo(handler)
    repo.top_tracks(limit=200, time_range="short_term")
    assert seen["time_range"] == "short_term"
    assert seen["limit"] == "50"


def test_top_artists_maps_artist_summary():
    payload = {
        "total": 1,
        "offset": 0,
        "items": [
            {
                "id": "a1",
                "name": "Artist",
                "uri": "spotify:artist:a1",
                "genres": ["rock"],
                "popularity": 70,
                "followers": {"total": 1000},
            }
        ],
    }
    repo = make_repo(lambda request: httpx.Response(200, json=payload))
    page = repo.top_artists()
    assert page["items"] == [
        {
            "id": "a1",
            "name": "Artist",
            "uri": "spotify:artist:a1",
            "genres": ["rock"],
            "popularity": 70,
            "followers": 1000,
        }
    ]


def test_save_tracks_chunks_of_50_via_put():
    repo, calls = recording_repo(lambda request: httpx.Response(200))
    assert repo.save_tracks([f"{i:022d}" for i in range(70)]) == 70
    assert [(m, len(b["ids"])) for m, p, b in calls if p == "/v1/me/tracks"] == [
        ("PUT", 50),
        ("PUT", 20),
    ]


def test_update_and_unfollow_playlist():
    repo, calls = recording_repo(lambda request: httpx.Response(200))
    repo.update_playlist("pl", {"name": "New", "public": False})
    repo.unfollow_playlist("pl")
    assert calls[0] == ("PUT", "/v1/playlists/pl", {"name": "New", "public": False})
    assert calls[1] == ("DELETE", "/v1/playlists/pl/followers", None)


def test_get_album_trims_payload():
    payload = {
        "id": "al",
        "name": "Album",
        "uri": "spotify:album:al",
        "artists": [{"name": "A"}],
        "release_date": "2020-01-01",
        "total_tracks": 12,
        "label": "Lbl",
        "tracks": {"items": []},
        "available_markets": ["US"] * 100,
    }
    repo = make_repo(lambda request: httpx.Response(200, json=payload))
    assert repo.get_album("al") == {
        "id": "al",
        "name": "Album",
        "uri": "spotify:album:al",
        "artists": ["A"],
        "release_date": "2020-01-01",
        "total_tracks": 12,
        "label": "Lbl",
    }


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
