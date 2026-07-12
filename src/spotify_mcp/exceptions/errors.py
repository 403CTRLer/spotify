class SpotifyMcpError(Exception):
    """Base class for all spotify-mcp errors."""


class AuthError(SpotifyMcpError):
    """Authentication, token, or auth-configuration problem. Messages are user-actionable."""


class ApiError(SpotifyMcpError):
    """Spotify Web API returned an error, or the HTTP call itself failed (status 0)."""

    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


class NotFoundError(ApiError):
    """Resource does not exist (bad playlist/track/album id)."""


class RateLimitError(ApiError):
    """Rate-limited beyond what bounded retries can absorb.

    `retry_after` carries the server's requested wait in seconds when known.
    """

    def __init__(self, message: str, status: int = 429, retry_after: int | None = None) -> None:
        super().__init__(message, status)
        self.retry_after = retry_after
