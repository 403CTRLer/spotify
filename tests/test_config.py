import pytest

from spotify_mcp.config.settings import DEFAULT_REDIRECT_URI, Settings
from spotify_mcp.exceptions.errors import AuthError


def test_env_wins_over_dotenv(tmp_path, monkeypatch):
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "# comment\nSPOTIFY_CLIENT_ID='file-id'\nSPOTIFY_REDIRECT_URI=http://127.0.0.1:9/cb\n"
    )
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "env-id")
    monkeypatch.delenv("SPOTIFY_REDIRECT_URI", raising=False)

    settings = Settings.from_env(dotenv_path=dotenv)
    assert settings.client_id == "env-id"  # env beats .env
    assert settings.redirect_uri == "http://127.0.0.1:9/cb"  # .env fills the gap


def test_dotenv_only_and_quote_stripping(tmp_path, monkeypatch):
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_REDIRECT_URI", raising=False)
    dotenv = tmp_path / ".env"
    dotenv.write_text('SPOTIFY_CLIENT_ID="quoted-id"\n')

    settings = Settings.from_env(dotenv_path=dotenv)
    assert settings.client_id == "quoted-id"
    assert settings.redirect_uri == DEFAULT_REDIRECT_URI


def test_missing_client_id_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    with pytest.raises(AuthError, match="SPOTIFY_CLIENT_ID"):
        Settings.from_env(dotenv_path=tmp_path / "absent.env")


def test_home_dotenv_fallback_when_cwd_has_none(tmp_path, monkeypatch):
    # review #12: MCP clients may launch the server with an arbitrary cwd
    import spotify_mcp.config.settings as settings_module

    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_REDIRECT_URI", raising=False)
    cwd = tmp_path / "random-cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)  # no ./.env here
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / ".env").write_text("SPOTIFY_CLIENT_ID=home-id\n")
    monkeypatch.setattr(settings_module, "DEFAULT_STATE_DIR", state_dir)

    assert Settings.from_env().client_id == "home-id"
