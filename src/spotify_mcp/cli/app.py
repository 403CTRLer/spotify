"""Developer CLI. The only layer that prints or prompts.

Handlers are plain (args) -> int functions so a future interactive menu can
dispatch to them without restructuring.
"""

import argparse
import json
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

    serve_main(verbosity=max(args.verbose, 1))  # server logs at least INFO (review #11)
    return 0


def _emit_json(args: argparse.Namespace, data: object) -> bool:
    """Print JSON and return True when --json was requested."""
    if getattr(args, "json", False):
        print(json.dumps(data, indent=2))
        return True
    return False


def cmd_playlists(args: argparse.Namespace) -> int:
    items = _service().all_playlists()
    if _emit_json(args, [p.model_dump() for p in items]):
        return 0
    for playlist in items:
        print(f"{playlist.name}  ({playlist.total_tracks} tracks)  [{playlist.id}]")
    return 0


def cmd_now(args: argparse.Namespace) -> int:
    data = _service().playback()
    if _emit_json(args, data):
        return 0
    state = data["state"]
    if not state or not state.get("track"):
        print("Nothing is playing.")
    else:
        track = state["track"]
        status = "Playing" if state["is_playing"] else "Paused"
        device = (state.get("device") or {}).get("name") or "unknown device"
        print(f"{status}: {track['name']} - {', '.join(track['artists'])}  [{device}]")
    for device in data["devices"]:
        marker = "*" if device["is_active"] else " "
        print(f"  {marker} {device['name']} ({device['type']})  vol={device['volume_percent']}")
    return 0


def cmd_play(args: argparse.Namespace) -> int:
    print(_service().play(args.item, args.device))
    return 0


def cmd_pause(args: argparse.Namespace) -> int:
    _service().pause()
    print("Paused.")
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    _service().skip_next()
    print("Skipped to next track.")
    return 0


def cmd_prev(args: argparse.Namespace) -> int:
    _service().skip_previous()
    print("Skipped to previous track.")
    return 0


def cmd_queue(args: argparse.Namespace) -> int:
    _service().queue_add(args.track)
    print("Added to queue.")
    return 0


def cmd_volume(args: argparse.Namespace) -> int:
    _service().set_volume(args.percent)
    print(f"Volume set to {args.percent}%.")
    return 0


def cmd_top(args: argparse.Namespace) -> int:
    service = _service()
    if args.kind == "tracks":
        page = service.top_tracks(args.range, args.limit)
        items: list[dict] = [t.model_dump() for t in page["items"]]
    else:
        items = list(service.top_artists(args.range, args.limit)["items"])
    if _emit_json(args, items):
        return 0
    for index, item in enumerate(items, 1):
        artists = f" - {', '.join(item['artists'])}" if item.get("artists") else ""
        print(f"{index:2}. {item['name']}{artists}")
    return 0


def cmd_like(args: argparse.Namespace) -> int:
    print(f"Saved {_service().save_library_tracks(args.tracks)} tracks to your library.")
    return 0


def cmd_unlike(args: argparse.Namespace) -> int:
    print(f"Removed {_service().remove_library_tracks(args.tracks)} tracks from your library.")
    return 0


def cmd_lookup(args: argparse.Namespace) -> int:
    data = _service().lookup(args.ref)
    if _emit_json(args, data):
        return 0
    for key, value in data.items():
        print(f"{key}: {value}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    results = _service().search(args.query, tuple(args.type or ["track"]), args.limit)
    if _emit_json(args, results):
        return 0
    for kind, items in results.items():
        print(f"{kind}:")
        for item in items:
            artists = f" - {', '.join(item['artists'])}" if item.get("artists") else ""
            print(f"  {item['name']}{artists}  [{item.get('uri') or item.get('id')}]")
    return 0


def cmd_tracks(args: argparse.Namespace) -> int:
    page = _service().playlist_items(args.playlist, limit=args.limit, offset=args.offset)
    items = [t.model_dump() for t in page["items"]]
    if _emit_json(args, {"total": page["total"], "offset": page["offset"], "items": items}):
        return 0
    for track in items:
        print(f"{track['name']} - {', '.join(track['artists'])}")
    print(f"({len(items)} of {page['total']} tracks)")
    return 0


def cmd_recent(args: argparse.Namespace) -> int:
    items = [
        {"played_at": item["played_at"], "track": item["track"].model_dump()}
        for item in _service().recently_played(args.limit)
    ]
    if _emit_json(args, items):
        return 0
    for item in items:
        track = item["track"]
        print(f"{item['played_at']}  {track['name']} - {', '.join(track['artists'])}")
    return 0


def cmd_create_playlist(args: argparse.Namespace) -> int:
    playlist = _service().create_playlist(args.name, args.description, args.public)
    if _emit_json(args, playlist.model_dump()):
        return 0
    print(f"Created {playlist.name!r}  [{playlist.id}]")
    return 0


def cmd_update_playlist(args: argparse.Namespace) -> int:
    _service().update_playlist(args.playlist, args.name, args.description, args.public)
    print("Playlist updated.")
    return 0


def cmd_delete_playlist(args: argparse.Namespace) -> int:
    service = _service()
    target = service.get_playlist(args.playlist)
    try:
        answer = input(f"Delete playlist {target.name!r} ({target.total_tracks} tracks)? [y/N] ")
    except EOFError:
        answer = ""
    if answer.strip().lower() not in {"y", "yes"}:
        print("Aborted.")
        return 1
    name = service.delete_playlist(args.playlist)
    print(f"Deleted {name!r}. (Spotify keeps deleted playlists recoverable for 90 days.)")
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
    ignore = [term for chunk in args.ignore or [] for term in chunk.split(",")]
    for name, status in _service().shuffle_all_owned(ignore):
        print(f"{status:>8}: {name}")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    name, count, skipped = _service().restore_snapshot(args.snapshot, force=args.force)
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
    try:
        answer = input(f"Delete ALL {total} saved tracks? This cannot be undone. [y/N] ")
    except EOFError:  # piped/closed stdin can never confirm a destructive action
        answer = ""
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
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON where supported"
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
        default=None,  # argparse appends INTO a list default, leaking across parses
        help="Playlists to skip: links, IDs, or partial names (repeatable or comma-separated)",
    )
    shuffle_all.set_defaults(func=cmd_shuffle_all)

    # -- playback (requires Spotify Premium) --
    sub.add_parser("now", help="Show playback state and available devices").set_defaults(
        func=cmd_now
    )
    play = sub.add_parser("play", help="Resume, or play a track/album/playlist/artist")
    play.add_argument("item", nargs="?", help="Link, URI, or track ID (omit to resume)")
    play.add_argument("--device", help="Device id from `now`")
    play.set_defaults(func=cmd_play)
    sub.add_parser("pause", help="Pause playback").set_defaults(func=cmd_pause)
    sub.add_parser("next", help="Skip to next track").set_defaults(func=cmd_next)
    sub.add_parser("prev", help="Skip to previous track").set_defaults(func=cmd_prev)
    queue = sub.add_parser("queue", help="Add a track to the playback queue")
    queue.add_argument("track", help="Track link, URI, or ID")
    queue.set_defaults(func=cmd_queue)
    volume = sub.add_parser("volume", help="Set playback volume")
    volume.add_argument("percent", type=int, help="0-100")
    volume.set_defaults(func=cmd_volume)

    # -- discovery and library --
    top = sub.add_parser("top", help="Your most-listened tracks or artists")
    top.add_argument("kind", choices=["tracks", "artists"])
    top.add_argument(
        "--range",
        default="medium",
        choices=["short", "medium", "long"],
        help="short ~4 weeks, medium ~6 months, long = years",
    )
    top.add_argument("--limit", type=int, default=20)
    top.set_defaults(func=cmd_top)

    search = sub.add_parser("search", help="Search the catalog")
    search.add_argument("query")
    search.add_argument(
        "--type",
        action="append",
        choices=["track", "playlist", "album", "artist"],
        help="Repeatable; default: track",
    )
    search.add_argument("--limit", type=int, default=10)
    search.set_defaults(func=cmd_search)

    lookup = sub.add_parser("lookup", help="Metadata for any Spotify link or URI")
    lookup.add_argument("ref", help="Track/album/artist/playlist URL or URI")
    lookup.set_defaults(func=cmd_lookup)

    tracks = sub.add_parser("tracks", help="List tracks in a playlist")
    tracks.add_argument("playlist", help="Playlist link, URI, or ID")
    tracks.add_argument("--limit", type=int, default=100)
    tracks.add_argument("--offset", type=int, default=0)
    tracks.set_defaults(func=cmd_tracks)

    recent = sub.add_parser("recent", help="Recently played tracks")
    recent.add_argument("--limit", type=int, default=20)
    recent.set_defaults(func=cmd_recent)

    like = sub.add_parser("like", help="Save tracks to your library")
    like.add_argument("tracks", nargs="+", help="Track links, URIs, or IDs")
    like.set_defaults(func=cmd_like)
    unlike = sub.add_parser("unlike", help="Remove tracks from your library")
    unlike.add_argument("tracks", nargs="+", help="Track links, URIs, or IDs")
    unlike.set_defaults(func=cmd_unlike)

    # -- playlist management --
    create = sub.add_parser("create-playlist", help="Create a new playlist")
    create.add_argument("name")
    create.add_argument("--description", default="")
    create.add_argument("--public", action="store_true")
    create.set_defaults(func=cmd_create_playlist)

    update = sub.add_parser("update-playlist", help="Change a playlist's details")
    update.add_argument("playlist", help="Playlist link, URI, or ID")
    update.add_argument("--name")
    update.add_argument("--description")
    visibility = update.add_mutually_exclusive_group()
    visibility.add_argument("--public", dest="public", action="store_true", default=None)
    visibility.add_argument("--private", dest="public", action="store_false")
    update.set_defaults(func=cmd_update_playlist)

    delete = sub.add_parser(
        "delete-playlist", help="Delete (unfollow) a playlist - asks for confirmation"
    )
    delete.add_argument("playlist", help="Playlist link, URI, or ID")
    delete.set_defaults(func=cmd_delete_playlist)

    restore = sub.add_parser("restore", help="Restore a playlist from a recovery snapshot")
    restore.add_argument("snapshot", help="Path to a snapshot JSON from ~/.spotify-mcp/recovery/")
    restore.add_argument(
        "--force",
        action="store_true",
        help="Restore even if the playlist gained tracks after the snapshot (they are removed)",
    )
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
