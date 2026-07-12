import asyncio

from spotify_mcp.mcp.server import build_server
from spotify_mcp.tools.capabilities import CAPABILITIES


def test_server_registers_the_registry_derived_tool_set():
    # FastMCP validates every signature at registration, so this also
    # proves all tool schemas are derivable
    server = build_server()
    tools = asyncio.run(server.list_tools())
    assert {tool.name for tool in tools} == set(CAPABILITIES)


def test_annotations_reflect_the_capability_registry():
    server = build_server()
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    for name, capability in CAPABILITIES.items():
        annotations = tools[name].annotations
        assert annotations is not None, name
        assert annotations.readOnlyHint == capability.read_only, name
        assert annotations.destructiveHint == capability.destructive, name
        assert annotations.idempotentHint == capability.idempotent, name
        assert annotations.openWorldHint is True, name


def test_every_tool_has_a_description():
    server = build_server()
    for tool in asyncio.run(server.list_tools()):
        assert tool.description and len(tool.description) > 15, tool.name


def test_server_publishes_instructions():
    server = build_server()
    assert server.instructions and "spotify-mcp auth" in server.instructions
