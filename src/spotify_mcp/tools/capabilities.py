"""Single source of truth for the capability surface.

Every MCP tool has a Capability record describing its behavior and required
OAuth scopes. The registry drives:

1. MCP ToolAnnotations (mcp/server.py) - read-only/destructive/idempotent
   hints clients use for autonomy decisions,
2. the scope audit test - auth.SCOPES must equal the union of all scopes
   declared here, so scope drift fails CI,
3. the capability tables in the documentation.

Kept separate from tool definitions on purpose: metadata about the surface,
not implementation.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Capability:
    read_only: bool
    destructive: bool = False
    idempotent: bool = False
    confirmation_required: bool = False
    scopes: frozenset[str] = field(default_factory=frozenset)


_PLAYLIST_WRITE = frozenset({"playlist-modify-public", "playlist-modify-private"})
_PLAYER_WRITE = frozenset({"user-modify-playback-state"})

CAPABILITIES: dict[str, Capability] = {
    # reads
    "user_profile": Capability(read_only=True, idempotent=True),
    "playlists": Capability(
        read_only=True,
        idempotent=True,
        scopes=frozenset({"playlist-read-private", "playlist-read-collaborative"}),
    ),
    "playlist_items": Capability(
        read_only=True, idempotent=True, scopes=frozenset({"playlist-read-private"})
    ),
    "library_tracks": Capability(
        read_only=True, idempotent=True, scopes=frozenset({"user-library-read"})
    ),
    "recent_history": Capability(
        read_only=True, idempotent=True, scopes=frozenset({"user-read-recently-played"})
    ),
    "top_items": Capability(read_only=True, idempotent=True, scopes=frozenset({"user-top-read"})),
    "search": Capability(read_only=True, idempotent=True),
    "lookup": Capability(
        read_only=True, idempotent=True, scopes=frozenset({"playlist-read-private"})
    ),
    "playback_state": Capability(
        read_only=True, idempotent=True, scopes=frozenset({"user-read-playback-state"})
    ),
    # playback control (Premium)
    "play": Capability(read_only=False, scopes=_PLAYER_WRITE),
    "pause": Capability(read_only=False, idempotent=True, scopes=_PLAYER_WRITE),
    "skip_next": Capability(read_only=False, scopes=_PLAYER_WRITE),
    "skip_previous": Capability(read_only=False, scopes=_PLAYER_WRITE),
    "queue_add": Capability(read_only=False, scopes=_PLAYER_WRITE),
    "set_volume": Capability(read_only=False, idempotent=True, scopes=_PLAYER_WRITE),
    # library writes (reversible)
    "save_to_library": Capability(
        read_only=False, idempotent=True, scopes=frozenset({"user-library-modify"})
    ),
    "remove_from_library": Capability(
        read_only=False,
        destructive=True,
        idempotent=True,
        scopes=frozenset({"user-library-modify"}),
    ),
    # playlist writes
    "create_playlist": Capability(read_only=False, scopes=_PLAYLIST_WRITE),
    "add_to_playlist": Capability(read_only=False, scopes=_PLAYLIST_WRITE),
    "remove_from_playlist": Capability(
        read_only=False, destructive=True, idempotent=True, scopes=_PLAYLIST_WRITE
    ),
    "update_playlist": Capability(read_only=False, idempotent=True, scopes=_PLAYLIST_WRITE),
    "delete_playlist": Capability(
        read_only=False,
        destructive=True,
        idempotent=True,
        confirmation_required=True,
        scopes=_PLAYLIST_WRITE,
    ),
    "shuffle_playlist": Capability(
        read_only=False, destructive=True, confirmation_required=True, scopes=_PLAYLIST_WRITE
    ),
}
