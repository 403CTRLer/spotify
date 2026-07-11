import base64
import contextlib
import hashlib
import json
import logging
import os
import secrets
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from spotify_mcp.config.settings import Settings
from spotify_mcp.exceptions.errors import AuthError

log = logging.getLogger(__name__)

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
SCOPES = (
    "playlist-read-private playlist-read-collaborative "
    "playlist-modify-public playlist-modify-private "
    "user-library-read user-library-modify "
    "user-read-currently-playing user-read-recently-played"
)
LOGIN_TIMEOUT_S = 300
_EXPIRY_MARGIN_S = 60


def make_challenge(verifier: str) -> str:
    """S256 code challenge per RFC 7636."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        params = parse_qs(urlparse(self.path).query)
        self.server.result = {k: v[0] for k, v in params.items()}  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Login complete. You can close this tab.")

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass  # silence default request logging


class SpotifyAuth:
    """OAuth Authorization Code + PKCE. No client secret, tokens cached on disk.

    The browser flow lives ONLY in login() (the CLI `auth` command); the MCP
    server never opens a browser - it raises an actionable AuthError instead.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache_path = settings.token_cache_path
        self._tokens: dict[str, Any] | None = None
        self._refresh_lock = threading.Lock()

    # -- interactive flow ---------------------------------------------------

    def login(self) -> None:
        verifier = secrets.token_urlsafe(64)
        state = secrets.token_urlsafe(16)
        params = {
            "client_id": self._settings.client_id,
            "response_type": "code",
            "redirect_uri": self._settings.redirect_uri,
            "state": state,
            "scope": SCOPES,
            "code_challenge_method": "S256",
            "code_challenge": make_challenge(verifier),
        }
        result = self._await_callback(f"{AUTH_URL}?{urlencode(params)}")

        if result.get("error"):
            raise AuthError(f"Spotify login failed: {result['error']}")
        if result.get("state") != state:
            raise AuthError("State mismatch in OAuth callback; aborting login.")
        code = result.get("code")
        if not code:
            raise AuthError("OAuth callback did not include an authorization code.")

        tokens = self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._settings.redirect_uri,
                "client_id": self._settings.client_id,
                "code_verifier": verifier,
            }
        )
        self._save(tokens)
        log.info("Authenticated; token cache at %s", self._cache_path)

    def _await_callback(self, url: str) -> dict[str, str]:
        parsed = urlparse(self._settings.redirect_uri)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 80
        server = HTTPServer((host, port), _CallbackHandler)
        server.result = None  # type: ignore[attr-defined]
        server.timeout = 5
        try:
            webbrowser.open(url)
            print(  # login() is CLI-only; stderr is safe even under MCP
                f"Complete the login in your browser. If it did not open, visit:\n{url}",
                file=sys.stderr,
            )
            deadline = time.monotonic() + LOGIN_TIMEOUT_S
            while server.result is None:  # type: ignore[attr-defined]
                if time.monotonic() > deadline:
                    raise AuthError(f"Login timed out after {LOGIN_TIMEOUT_S}s.")
                server.handle_request()
            return server.result  # type: ignore[attr-defined]
        finally:
            server.server_close()

    # -- token lifecycle ----------------------------------------------------

    def get_token(self) -> str:
        tokens = self._tokens or self._load()
        if not tokens:
            raise AuthError("Not authenticated. Run `spotify-mcp auth` first.")
        if not set(SCOPES.split()) <= set((tokens.get("scope") or "").split()):
            raise AuthError("Cached token is missing required scopes. Run `spotify-mcp auth`.")
        if tokens["expires_at"] - _EXPIRY_MARGIN_S < time.time():
            return self.refresh_now()
        return tokens["access_token"]

    def refresh_now(self) -> str:
        """Refresh the access token, serialized against concurrent callers.

        Spotify rotates refresh tokens: two concurrent refreshes present the
        same (now dead) token, which can invalidate the whole grant family.
        Inside the lock the cache is re-read from disk; if another thread or
        process already refreshed, that token is reused instead (review #3).
        """
        entry_token = (self._tokens or {}).get("access_token")
        with self._refresh_lock:
            tokens = self._load()
            if (
                tokens
                and tokens.get("access_token")
                and tokens["access_token"] != entry_token
                and tokens.get("expires_at", 0) - _EXPIRY_MARGIN_S > time.time()
            ):
                return tokens["access_token"]  # someone else refreshed while we waited
            if not tokens or not tokens.get("refresh_token"):
                raise AuthError("No refresh token available. Run `spotify-mcp auth`.")
            log.info("Refreshing access token")
            new = self._token_request(
                {
                    "grant_type": "refresh_token",
                    "refresh_token": tokens["refresh_token"],
                    "client_id": self._settings.client_id,
                }
            )
            # Spotify rotates refresh tokens; keep the old one when omitted
            new.setdefault("refresh_token", tokens["refresh_token"])
            new.setdefault("scope", tokens.get("scope", ""))
            self._save(new)
            return new["access_token"]

    def _token_request(self, data: dict[str, str]) -> dict[str, Any]:
        try:
            resp = httpx.post(TOKEN_URL, data=data, timeout=30)
        except httpx.HTTPError as exc:  # keep network failures inside the error family
            raise AuthError(f"Could not reach Spotify's token endpoint: {exc}") from exc
        if resp.status_code != 200:
            raise AuthError(f"Token request failed ({resp.status_code}): {resp.text}")
        payload: dict[str, Any] = resp.json()
        payload["expires_at"] = time.time() + payload.get("expires_in", 3600)
        return payload

    # -- cache --------------------------------------------------------------

    def _save(self, tokens: dict[str, Any]) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(tokens), encoding="utf-8")
        os.replace(tmp, self._cache_path)
        with contextlib.suppress(OSError):
            os.chmod(self._cache_path, 0o600)  # best effort; limited semantics on Windows
        self._tokens = tokens

    def _load(self) -> dict[str, Any] | None:
        try:
            tokens = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        # a malformed cache (missing keys, wrong types) is the same as no cache
        if (
            not isinstance(tokens, dict)
            or not isinstance(tokens.get("access_token"), str)
            or not isinstance(tokens.get("expires_at"), int | float)
        ):
            return None
        self._tokens = tokens
        return self._tokens
