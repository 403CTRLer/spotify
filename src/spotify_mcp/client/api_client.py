import logging
import time
from collections.abc import Iterator
from typing import Any, Protocol

import httpx

from spotify_mcp.exceptions.errors import ApiError, AuthError, NotFoundError, RateLimitError

log = logging.getLogger(__name__)

BASE_URL = "https://api.spotify.com/v1"
MAX_RATE_LIMIT_RETRIES = 3
MAX_RETRY_AFTER_S = 30


class TokenProvider(Protocol):
    def get_token(self) -> str: ...
    def refresh_now(self) -> str: ...


class SpotifyApiClient:
    """HTTP mechanics only: bearer auth, retries, pagination. No endpoint knowledge."""

    def __init__(self, auth: TokenProvider, http: httpx.Client | None = None) -> None:
        self._auth = auth
        self._http = http or httpx.Client(base_url=BASE_URL, timeout=30)

    def get(self, path: str, **params: Any) -> Any:
        return self._request("GET", path, params=params or None)

    def post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        return self._request("POST", path, json=json)

    def put(self, path: str, json: dict[str, Any] | None = None) -> Any:
        return self._request("PUT", path, json=json)

    def delete(self, path: str, json: dict[str, Any] | None = None) -> Any:
        return self._request("DELETE", path, json=json)

    def paginate(self, path: str, **params: Any) -> Iterator[dict[str, Any]]:
        """Yield items across pages, following Spotify's absolute `next` URLs."""
        page = self.get(path, **params)
        while page:
            yield from page.get("items") or []
            next_url = page.get("next")
            page = self._request("GET", next_url) if next_url else None

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        refreshed = False
        rate_limit_attempts = 0
        while True:
            headers = {"Authorization": f"Bearer {self._auth.get_token()}"}
            log.debug("%s %s", method, path)
            try:
                resp = self._http.request(method, path, params=params, json=json, headers=headers)
            except httpx.HTTPError as exc:
                raise ApiError(f"HTTP error calling Spotify: {exc}") from exc

            if resp.status_code == 401 and not refreshed:
                refreshed = True
                self._auth.refresh_now()
                continue
            if resp.status_code == 429 and rate_limit_attempts < MAX_RATE_LIMIT_RETRIES:
                rate_limit_attempts += 1
                try:
                    delay = int(resp.headers.get("Retry-After") or 1)
                except ValueError:  # e.g. an HTTP-date; retry conservatively
                    delay = 1
                if delay > MAX_RETRY_AFTER_S:
                    # retrying before the server's window would just 429 again;
                    # fail fast and tell the caller how long to wait (review #5)
                    raise RateLimitError(
                        f"Spotify requested a {delay}s wait (cap is {MAX_RETRY_AFTER_S}s); "
                        "not retrying.",
                        retry_after=delay,
                    )
                log.warning(
                    "Rate limited; retrying in %ss (attempt %s/%s)",
                    delay,
                    rate_limit_attempts,
                    MAX_RATE_LIMIT_RETRIES,
                )
                time.sleep(delay)
                continue
            return self._handle(resp)

    def _handle(self, resp: httpx.Response) -> Any:
        if resp.status_code == 401:
            raise AuthError("Spotify rejected credentials after a refresh. Run `spotify-mcp auth`.")
        if resp.status_code == 404:
            raise NotFoundError(self._error_message(resp), status=404)
        if resp.status_code == 429:
            raise RateLimitError("Still rate-limited by Spotify after retries.", status=429)
        if resp.status_code >= 400:
            raise ApiError(self._error_message(resp), status=resp.status_code)
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    @staticmethod
    def _error_message(resp: httpx.Response) -> str:
        try:
            return resp.json()["error"]["message"]
        except (ValueError, KeyError, TypeError):
            return f"Spotify API error {resp.status_code}"
