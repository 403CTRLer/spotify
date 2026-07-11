import asyncio

from spotify_mcp.mcp.server import build_server

EXPECTED_TOOLS = {
    # reads
    "user_profile",
    "currently_playing",
    "playlists",
    "playlist_items",
    "search",
    "library_tracks",
    "recent_history",
    "top_items",
    "lookup",
    "playback_state",
    # playback control
    "play",
    "pause",
    "skip_next",
    "skip_previous",
    "queue_add",
    "set_volume",
    # library writes
    "save_to_library",
    "remove_from_library",
    # playlist writes
    "create_playlist",
    "add_to_playlist",
    "remove_from_playlist",
    "update_playlist",
    "delete_playlist",
    "shuffle_playlist",
}


def test_server_registers_exactly_the_expected_tools():
    # FastMCP validates every signature at registration, so this also
    # proves all tool schemas are derivable
    server = build_server()
    tools = asyncio.run(server.list_tools())
    assert {tool.name for tool in tools} == EXPECTED_TOOLS
    assert len(tools) == 24


def test_every_tool_has_a_description():
    server = build_server()
    tools = asyncio.run(server.list_tools())
    for tool in tools:
        assert tool.description and len(tool.description) > 15, tool.name
