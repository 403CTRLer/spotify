import json

import httpx
import pytest

from spotify_mcp.client.api_client import BASE_URL, SpotifyApiClient
from spotify_mcp.exceptions.errors import ApiError, AuthError, NotFoundError, RateLimitError


class FakeAuth:
    def __init__(self):
        self.token = "tok-1"
        self.refreshes = 0

    def get_token(self) -> str:
        return self.token

    def refresh_now(self) -> str:
        self.refreshes += 1
        self.token = f"tok-{self.refreshes + 1}"
        return self.token


def make_client(handler):
    auth = FakeAuth()
    http = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    return SpotifyApiClient(auth, http=http), auth


def test_bearer_header_sent():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["Authorization"]
        return httpx.Response(200, json={"ok": True})

    client, _ = make_client(handler)
    assert client.get("/me") == {"ok": True}
    assert seen["auth"] == "Bearer tok-1"


def test_401_refreshes_and_retries_once():
    calls = []

    def handler(request):
        calls.append(request.headers["Authorization"])
        if len(calls) == 1:
            return httpx.Response(401, json={"error": {"message": "expired"}})
        return httpx.Response(200, json={"ok": True})

    client, auth = make_client(handler)
    assert client.get("/me") == {"ok": True}
    assert auth.refreshes == 1
    assert calls == ["Bearer tok-1", "Bearer tok-2"]


def test_second_401_raises_auth_error():
    def handler(request):
        return httpx.Response(401, json={"error": {"message": "nope"}})

    client, auth = make_client(handler)
    with pytest.raises(AuthError):
        client.get("/me")
    assert auth.refreshes == 1  # exactly one refresh attempt, no loop


def test_429_retries_then_succeeds():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"ok": True})

    client, _ = make_client(handler)
    assert client.get("/search") == {"ok": True}
    assert len(calls) == 3


def test_persistent_429_raises_rate_limit_error():
    def handler(request):
        return httpx.Response(429, headers={"Retry-After": "0"})

    client, _ = make_client(handler)
    with pytest.raises(RateLimitError):
        client.get("/search")


def test_404_raises_not_found_with_spotify_message():
    def handler(request):
        return httpx.Response(404, json={"error": {"message": "Invalid playlist Id"}})

    client, _ = make_client(handler)
    with pytest.raises(NotFoundError, match="Invalid playlist Id"):
        client.get("/playlists/bad")


def test_other_4xx_raises_api_error_with_status():
    def handler(request):
        return httpx.Response(403, json={"error": {"message": "Forbidden"}})

    client, _ = make_client(handler)
    with pytest.raises(ApiError, match="Forbidden") as exc_info:
        client.get("/me")
    assert exc_info.value.status == 403


def test_204_returns_none():
    def handler(request):
        return httpx.Response(204)

    client, _ = make_client(handler)
    assert client.get("/me/player/currently-playing") is None


def test_transport_error_wrapped_as_api_error():
    def handler(request):
        raise httpx.ConnectError("boom")

    client, _ = make_client(handler)
    with pytest.raises(ApiError, match="HTTP error"):
        client.get("/me")


def test_paginate_follows_next_urls():
    def handler(request):
        if request.url.params.get("offset") != "2":
            return httpx.Response(
                200,
                json={"items": [{"n": 1}, {"n": 2}], "next": f"{BASE_URL}/me/playlists?offset=2"},
            )
        return httpx.Response(200, json={"items": [{"n": 3}], "next": None})

    client, _ = make_client(handler)
    assert list(client.paginate("/me/playlists", limit=2)) == [{"n": 1}, {"n": 2}, {"n": 3}]


def test_post_sends_json_body():
    def handler(request):
        assert json.loads(request.content) == {"uris": ["a"]}
        return httpx.Response(201, json={"snapshot_id": "s"})

    client, _ = make_client(handler)
    assert client.post("/playlists/x/tracks", json={"uris": ["a"]}) == {"snapshot_id": "s"}
