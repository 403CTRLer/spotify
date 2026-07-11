import os
from dataclasses import dataclass, field
from pathlib import Path

from spotify_mcp.exceptions.errors import AuthError

DEFAULT_REDIRECT_URI = "http://127.0.0.1:8888/callback"
DEFAULT_STATE_DIR = Path.home() / ".spotify-mcp"


def _load_dotenv(path: Path) -> dict[str, str]:
    # ponytail: naive .env parser, swap for python-dotenv if quoting ever bites
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


@dataclass(frozen=True)
class Settings:
    client_id: str
    redirect_uri: str = DEFAULT_REDIRECT_URI
    state_dir: Path = field(default=DEFAULT_STATE_DIR)

    @property
    def token_cache_path(self) -> Path:
        return self.state_dir / "tokens.json"

    @property
    def recovery_dir(self) -> Path:
        return self.state_dir / "recovery"

    @classmethod
    def from_env(cls, dotenv_path: Path | None = None) -> "Settings":
        """Load settings from the environment, then ./.env, then ~/.spotify-mcp/.env.

        The home fallback matters for MCP clients that launch the server
        without setting a working directory (review #12)."""
        dotenv = _load_dotenv(dotenv_path or Path(".env"))
        if not dotenv and dotenv_path is None:
            dotenv = _load_dotenv(DEFAULT_STATE_DIR / ".env")

        def get(name: str) -> str | None:
            return os.environ.get(name) or dotenv.get(name)

        client_id = get("SPOTIFY_CLIENT_ID")
        if not client_id:
            raise AuthError(
                "SPOTIFY_CLIENT_ID is not set. Copy .env.example to .env and fill it in."
            )
        return cls(
            client_id=client_id,
            redirect_uri=get("SPOTIFY_REDIRECT_URI") or DEFAULT_REDIRECT_URI,
        )
