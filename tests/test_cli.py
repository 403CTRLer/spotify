import pytest

import spotify_mcp.cli.app as cli
from spotify_mcp.exceptions.errors import AuthError


class StubService:
    def __init__(self, saved_total=3):
        self.saved_total = saved_total
        self.cleared = False

    def saved_tracks(self, limit=50, offset=0):
        return {"total": self.saved_total, "offset": 0, "items": []}

    def clear_saved_tracks(self):
        self.cleared = True
        return self.saved_total


def test_ignore_default_does_not_leak_across_parses():
    # review #10: argparse appends into a shared list default
    parser = cli.build_parser()
    first = parser.parse_args(["shuffle-all", "--ignore", "chill"])
    second = parser.parse_args(["shuffle-all"])
    assert first.ignore == ["chill"]
    assert not second.ignore  # must not have accumulated "chill"


def test_clear_liked_aborts_on_eof(monkeypatch, capsys):
    # review #15: piped/closed stdin must abort, not traceback
    stub = StubService()
    monkeypatch.setattr(cli, "_service", lambda: stub)

    def eof(prompt):
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)
    args = cli.build_parser().parse_args(["clear-liked"])
    assert args.func(args) == 1
    assert not stub.cleared
    assert "Aborted." in capsys.readouterr().out


def test_clear_liked_refusal_never_calls_service(monkeypatch, capsys):
    stub = StubService()
    monkeypatch.setattr(cli, "_service", lambda: stub)
    monkeypatch.setattr("builtins.input", lambda prompt: "no")
    args = cli.build_parser().parse_args(["clear-liked"])
    assert args.func(args) == 1
    assert not stub.cleared


def test_main_maps_domain_errors_to_exit_1(monkeypatch, capsys):
    def raise_auth():
        raise AuthError("Not authenticated. Run `spotify-mcp auth` first.")

    monkeypatch.setattr(cli, "_service", raise_auth)
    assert cli.main(["playlists"]) == 1
    assert "Not authenticated" in capsys.readouterr().err


def test_shuffle_force_flag_wired_through(monkeypatch):
    seen = {}

    class ShuffleStub:
        def shuffle_playlist(self, ref, force=False):
            seen["force"] = force
            return 1

    monkeypatch.setattr(cli, "_service", lambda: ShuffleStub())
    args = cli.build_parser().parse_args(["shuffle", "x" * 22, "--force"])
    assert args.func(args) == 0
    assert seen["force"] is True


@pytest.mark.parametrize(
    "argv",
    [["mix", "--into", "t"], ["restore"], ["shuffle"], ["queue"], ["volume"], ["top"]],
)
def test_missing_required_args_exit_2(argv):
    with pytest.raises(SystemExit) as exc_info:
        cli.build_parser().parse_args(argv)
    assert exc_info.value.code == 2


def test_json_flag_emits_machine_readable_lookup(monkeypatch, capsys):
    import json

    class LookupStub:
        def lookup(self, ref):
            return {"type": "track", "name": "Song", "artists": ["A"]}

    monkeypatch.setattr(cli, "_service", lambda: LookupStub())
    assert cli.main(["--json", "lookup", "spotify:track:" + "t" * 22]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "type": "track",
        "name": "Song",
        "artists": ["A"],
    }


def test_play_wires_item_and_device(monkeypatch, capsys):
    seen = {}

    class PlayStub:
        def play(self, item, device_id):
            seen["args"] = (item, device_id)
            return "Playing track x."

    monkeypatch.setattr(cli, "_service", lambda: PlayStub())
    assert cli.main(["play", "t" * 22, "--device", "d1"]) == 0
    assert seen["args"] == ("t" * 22, "d1")


def test_delete_playlist_refusal_makes_no_call(monkeypatch, capsys):
    from spotify_mcp.models.schemas import Playlist

    class DeleteStub:
        deleted = False

        def get_playlist(self, ref):
            return Playlist(id="p" * 22, uri="u", name="Mix", total_tracks=3)

        def delete_playlist(self, ref):
            self.deleted = True
            return "Mix"

    stub = DeleteStub()
    monkeypatch.setattr(cli, "_service", lambda: stub)
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    assert cli.main(["delete-playlist", "p" * 22]) == 1
    assert not stub.deleted
    assert "Aborted." in capsys.readouterr().out


def test_update_playlist_visibility_flags(monkeypatch):
    seen = {}

    class UpdateStub:
        def update_playlist(self, ref, name, description, public):
            seen["public"] = public

    monkeypatch.setattr(cli, "_service", lambda: UpdateStub())
    cli.main(["update-playlist", "p" * 22, "--private"])
    assert seen["public"] is False
    cli.main(["update-playlist", "p" * 22, "--name", "X"])
    assert seen["public"] is None
