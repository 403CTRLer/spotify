class SpotifyMcpError(Exception):
    """Base class for all spotify-mcp errors."""


class AuthError(SpotifyMcpError):
    """Authentication, token, or auth-configuration problem. Messages are user-actionable."""


class LocalTracksError(SpotifyMcpError):
    """A destructive playlist rewrite would permanently drop local/unavailable
    tracks (the Web API cannot re-add them)."""


class ApiError(SpotifyMcpError):
    """Spotify Web API returned an error, or the HTTP call itself failed (status 0)."""

    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


class NotFoundError(ApiError):
    """Resource does not exist (bad playlist/track/album id)."""


class RateLimitError(ApiError):
    """Still rate-limited after bounded retries."""
