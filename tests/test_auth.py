import json
import threading
import time

import pytest

from spotify_mcp.auth.oauth import SCOPES, SpotifyAuth, make_challenge, parse_callback
from spotify_mcp.config.settings import Settings
from spotify_mcp.exceptions.errors import AuthError


@pytest.fixture
def auth(tmp_path):
    return SpotifyAuth(Settings(client_id="cid", state_dir=tmp_path))


def _tokens(**overrides):
    base = {
        "access_token": "at-1",
        "refresh_token": "rt-1",
        "scope": SCOPES,
        "expires_at": time.time() + 3600,
    }
    return base | overrides


def test_rfc7636_appendix_b_vector():
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    assert make_challenge(verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_cache_roundtrip(auth, tmp_path):
    tokens = _tokens()
    auth._save(tokens)
    fresh = SpotifyAuth(Settings(client_id="cid", state_dir=tmp_path))
    assert fresh.get_token() == "at-1"
    assert json.loads((tmp_path / "tokens.json").read_text()) == tokens


def test_missing_cache_raises(auth):
    with pytest.raises(AuthError, match="spotify-mcp auth"):
        auth.get_token()


def test_missing_scopes_raises(auth):
    auth._save(_tokens(scope="user-library-read"))
    with pytest.raises(AuthError, match="scopes"):
        auth.get_token()


def test_expired_token_triggers_refresh(auth, monkeypatch):
    auth._save(_tokens(expires_at=time.time() - 10))
    monkeypatch.setattr(
        auth, "_token_request", lambda data: _tokens(access_token="at-2", refresh_token="rt-2")
    )
    assert auth.get_token() == "at-2"


def test_fresh_token_does_not_refresh(auth, monkeypatch):
    auth._save(_tokens())

    def boom(data):
        raise AssertionError("refresh should not run")

    monkeypatch.setattr(auth, "_token_request", boom)
    assert auth.get_token() == "at-1"


def test_refresh_keeps_old_refresh_token_when_omitted(auth, monkeypatch):
    auth._save(_tokens())
    response = {"access_token": "at-2", "expires_at": time.time() + 3600}
    monkeypatch.setattr(auth, "_token_request", lambda data: dict(response))
    auth.refresh_now()
    assert auth._load()["refresh_token"] == "rt-1"  # rotation-safe


def test_refresh_adopts_rotated_refresh_token(auth, monkeypatch):
    auth._save(_tokens())
    response = _tokens(access_token="at-2", refresh_token="rt-2")
    monkeypatch.setattr(auth, "_token_request", lambda data: dict(response))
    auth.refresh_now()
    assert auth._load()["refresh_token"] == "rt-2"


def test_network_failure_during_token_request_raises_auth_error(auth, monkeypatch):
    # review #4a: httpx transport errors must not escape the SpotifyMcpError family
    import httpx

    import spotify_mcp.auth.oauth as oauth_module

    def explode(*args, **kwargs):
        raise httpx.ConnectError("network down")

    monkeypatch.setattr(oauth_module.httpx, "post", explode)
    with pytest.raises(AuthError, match="token endpoint"):
        auth._token_request({"grant_type": "refresh_token"})


def test_malformed_cache_is_treated_as_unauthenticated(auth, tmp_path):
    # review #4b: a valid-JSON-but-wrong-shape cache must not raise KeyError
    (tmp_path / "tokens.json").write_text("{}")
    with pytest.raises(AuthError, match="spotify-mcp auth"):
        auth.get_token()
    (tmp_path / "tokens.json").write_text('{"access_token": 42, "expires_at": "soon"}')
    with pytest.raises(AuthError, match="spotify-mcp auth"):
        auth.get_token()


def test_concurrent_refresh_hits_token_endpoint_once(auth, monkeypatch):
    # review #3: concurrent refreshes must not both present the same rotating
    # refresh token - the second caller reuses the first caller's result
    auth._save(_tokens(expires_at=time.time() - 10))
    calls = []
    second_entered = threading.Event()

    def slow_refresh(data):
        calls.append(data["refresh_token"])
        second_entered.wait(timeout=5)  # hold the lock until thread 2 is in refresh_now
        time.sleep(0.05)  # let thread 2 capture its entry token and block on the lock
        return _tokens(access_token="at-new", refresh_token="rt-new")

    monkeypatch.setattr(auth, "_token_request", slow_refresh)
    results = []

    def first():
        results.append(auth.refresh_now())

    def second():
        second_entered.set()
        results.append(auth.refresh_now())

    t1 = threading.Thread(target=first)
    t2 = threading.Thread(target=second)
    t1.start()
    time.sleep(0.02)  # ensure t1 acquires the lock first
    t2.start()
    t1.join()
    t2.join()

    assert calls == ["rt-1"]  # exactly one HTTP refresh, with the pre-rotation token
    assert results == ["at-new", "at-new"]


def test_file_lock_serializes_refresh_across_instances(tmp_path, monkeypatch):
    # cross-process race remediation: two SpotifyAuth instances (as CLI + MCP
    # server would be) share only the cache file - the interprocess file lock
    # plus disk re-read must yield exactly ONE HTTP refresh
    settings = Settings(client_id="cid", state_dir=tmp_path)
    a, b = SpotifyAuth(settings), SpotifyAuth(settings)
    a._save(_tokens(expires_at=time.time() - 10))
    b._load()  # b now also holds the stale token in memory
    calls = []
    b_started = threading.Event()

    def slow_refresh(data):
        calls.append(data["refresh_token"])
        b_started.wait(timeout=5)
        time.sleep(0.1)  # keep the file lock held while b blocks on it
        return _tokens(access_token="at-new", refresh_token="rt-new")

    monkeypatch.setattr(a, "_token_request", slow_refresh)
    monkeypatch.setattr(b, "_token_request", slow_refresh)
    results = []

    def run_a():
        results.append(a.refresh_now())

    def run_b():
        b_started.set()
        results.append(b.refresh_now())

    t1, t2 = threading.Thread(target=run_a), threading.Thread(target=run_b)
    t1.start()
    time.sleep(0.03)  # a acquires the locks first
    t2.start()
    t1.join()
    t2.join()

    assert calls == ["rt-1"]  # one refresh total, across both instances
    assert results == ["at-new", "at-new"]


def test_refresh_reuses_token_refreshed_by_another_process(auth, tmp_path, monkeypatch):
    # instance holds a stale in-memory token; another process already wrote a
    # fresh cache to disk - refresh_now must reuse it without an HTTP call
    auth._save(_tokens(expires_at=time.time() - 10))  # stale, also sets in-memory state
    fresh = _tokens(access_token="at-other-proc", refresh_token="rt-other-proc")
    (tmp_path / "tokens.json").write_text(json.dumps(fresh))

    def boom(data):
        raise AssertionError("no HTTP refresh should happen")

    monkeypatch.setattr(auth, "_token_request", boom)
    assert auth.refresh_now() == "at-other-proc"


@pytest.mark.parametrize(
    ("request_path", "expected"),
    [
        ("/favicon.ico", None),  # review #9: stray requests must not end the wait
        ("/callback", None),  # right path but no code/error yet
        ("/other?code=x", None),
        ("/callback?code=abc&state=s1", {"code": "abc", "state": "s1"}),
        ("/callback/?error=access_denied", {"error": "access_denied"}),
    ],
)
def test_parse_callback_filters_non_callback_requests(request_path, expected):
    assert parse_callback(request_path, "/callback") == expected


def test_bind_failure_raises_auth_error(auth, monkeypatch):
    import spotify_mcp.auth.oauth as oauth_module

    def refuse(*args, **kwargs):
        raise OSError(98, "Address already in use")

    monkeypatch.setattr(oauth_module, "HTTPServer", refuse)
    with pytest.raises(AuthError, match="Cannot listen"):
        auth._await_callback("https://example.test/authorize")


def test_login_rejects_state_mismatch(auth, monkeypatch):
    monkeypatch.setattr(auth, "_await_callback", lambda url: {"code": "c", "state": "tampered"})
    with pytest.raises(AuthError, match="State mismatch"):
        auth.login()


def test_login_surfaces_provider_error(auth, monkeypatch):
    monkeypatch.setattr(auth, "_await_callback", lambda url: {"error": "access_denied"})
    with pytest.raises(AuthError, match="access_denied"):
        auth.login()
