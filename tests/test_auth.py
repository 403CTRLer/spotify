import json
import time

import pytest

from spotify_mcp.auth.oauth import SCOPES, SpotifyAuth, make_challenge
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


def test_login_rejects_state_mismatch(auth, monkeypatch):
    monkeypatch.setattr(auth, "_await_callback", lambda url: {"code": "c", "state": "tampered"})
    with pytest.raises(AuthError, match="State mismatch"):
        auth.login()


def test_login_surfaces_provider_error(auth, monkeypatch):
    monkeypatch.setattr(auth, "_await_callback", lambda url: {"error": "access_denied"})
    with pytest.raises(AuthError, match="access_denied"):
        auth.login()
