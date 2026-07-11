"""Developer CLI. The only layer that prints or prompts.

Handlers are plain (args) -> int functions so a future interactive menu can
dispatch to them without restructuring.
"""

import argparse
import sys

from spotify_mcp.auth.oauth import SpotifyAuth
from spotify_mcp.client.api_client import SpotifyApiClient
from spotify_mcp.config.settings import Settings
from spotify_mcp.exceptions.errors import SpotifyMcpError
from spotify_mcp.repository.spotify import SpotifyApiRepository
from spotify_mcp.services.service import SpotifyService
from spotify_mcp.utils.logging import configure_logging


def _service() -> SpotifyService:
    settings = Settings.from_env()
    repo = SpotifyApiRepository(SpotifyApiClient(SpotifyAuth(settings)))
    return SpotifyService(repo, recovery_dir=settings.recovery_dir)


def cmd_auth(args: argparse.Namespace) -> int:
    SpotifyAuth(Settings.from_env()).login()
    user = _service().me()
    print(f"Logged in as {user.display_name or user.id}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from spotify_mcp.mcp.server import main as serve_main  # lazy: CLI cmds skip MCP import

    serve_main()
    return 0


def cmd_playlists(args: argparse.Namespace) -> int:
    for playlist in _service().all_playlists():
        print(f"{playlist.name}  ({playlist.total_tracks} tracks)  [{playlist.id}]")
    return 0


def cmd_mix(args: argparse.Namespace) -> int:
    added, dupes = _service().mix_playlists(args.sources, args.into)
    print(f"Added {added} unique tracks ({dupes} duplicates skipped).")
    return 0


def cmd_shuffle(args: argparse.Namespace) -> int:
    count = _service().shuffle_playlist(args.playlist, force=args.force)
    print(f"Shuffled {count} tracks.")
    return 0


def cmd_shuffle_all(args: argparse.Namespace) -> int:
    ignore = [term for chunk in args.ignore for term in chunk.split(",")]
    for name, status in _service().shuffle_all_owned(ignore):
        print(f"{status:>8}: {name}")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    name, count, skipped = _service().restore_snapshot(args.snapshot)
    print(f"Restored {count} tracks to {name!r}.")
    if skipped:
        print(f"Note: {len(skipped)} local/unavailable track(s) could not be restored via the API.")
    return 0


def cmd_liked_to_playlist(args: argparse.Namespace) -> int:
    count = _service().saved_to_playlist(args.target)
    print(f"Added {count} liked tracks.")
    return 0


def cmd_clear_liked(args: argparse.Namespace) -> int:
    service = _service()
    total = service.saved_tracks(limit=1)["total"]
    if total == 0:
        print("No saved tracks.")
        return 0
    answer = input(f"Delete ALL {total} saved tracks? This cannot be undone. [y/N] ")
    if answer.strip().lower() not in {"y", "yes"}:
        print("Aborted.")
        return 1
    print(f"Removed {service.clear_saved_tracks()} saved tracks.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spotify-mcp", description="Spotify service CLI + MCP server"
    )
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="-v for INFO, -vv for DEBUG logs"
    )
    sub = parser.add_subparsers(required=True)

    sub.add_parser("auth", help="Log in to Spotify (PKCE, opens browser)").set_defaults(
        func=cmd_auth
    )
    sub.add_parser("serve", help="Run the MCP server on stdio").set_defaults(func=cmd_serve)
    sub.add_parser("playlists", help="List your playlists").set_defaults(func=cmd_playlists)

    mix = sub.add_parser("mix", help="Merge playlists/albums/tracks into one playlist")
    mix.add_argument("sources", nargs="+", help="Source links, URIs, or playlist IDs")
    mix.add_argument("--into", required=True, help="Target playlist (link, URI, or ID)")
    mix.set_defaults(func=cmd_mix)

    shuffle = sub.add_parser("shuffle", help="Persistently shuffle a playlist")
    shuffle.add_argument("playlist", help="Playlist link, URI, or ID")
    shuffle.add_argument(
        "--force",
        action="store_true",
        help="Shuffle even if local/unavailable tracks would be permanently dropped",
    )
    shuffle.set_defaults(func=cmd_shuffle)

    shuffle_all = sub.add_parser("shuffle-all", help="Shuffle every playlist you own")
    shuffle_all.add_argument(
        "--ignore",
        action="append",
        default=[],
        help="Playlists to skip: links, IDs, or partial names (repeatable or comma-separated)",
    )
    shuffle_all.set_defaults(func=cmd_shuffle_all)

    restore = sub.add_parser("restore", help="Restore a playlist from a recovery snapshot")
    restore.add_argument("snapshot", help="Path to a snapshot JSON from ~/.spotify-mcp/recovery/")
    restore.set_defaults(func=cmd_restore)

    liked = sub.add_parser("liked-to-playlist", help="Copy all liked songs into a playlist")
    liked.add_argument("target", help="Target playlist (link, URI, or ID)")
    liked.set_defaults(func=cmd_liked_to_playlist)

    sub.add_parser(
        "clear-liked", help="Remove ALL liked songs (asks for confirmation)"
    ).set_defaults(func=cmd_clear_liked)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.verbose)
    try:
        return args.func(args)
    except (SpotifyMcpError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
