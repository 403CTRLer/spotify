import asyncio

from spotify_mcp.mcp.server import build_server

EXPECTED_TOOLS = {
    "user_profile",
    "currently_playing",
    "playlists",
    "playlist_items",
    "search",
    "create_playlist",
    "add_to_playlist",
    "remove_from_playlist",
    "library_tracks",
    "recent_history",
}


def test_server_registers_exactly_the_ten_tools():
    # FastMCP validates every signature at registration, so this also
    # proves all tool schemas are derivable
    server = build_server()
    tools = asyncio.run(server.list_tools())
    assert {tool.name for tool in tools} == EXPECTED_TOOLS
