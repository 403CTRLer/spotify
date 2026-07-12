from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from spotify_mcp.tools.capabilities import CAPABILITIES
from spotify_mcp.tools.definitions import ALL_TOOLS
from spotify_mcp.utils.logging import configure_logging

INSTRUCTIONS = """Spotify connector. Requires prior authentication: if tools
fail with "Not authenticated", the user must run `spotify-mcp auth` in a
terminal once. References may be Spotify URLs or spotify: URIs; bare
22-character IDs are accepted only where a parameter names the type (e.g. a
`playlist` or `tracks` parameter). Playback control tools require Spotify
Premium. Destructive tools (delete_playlist, shuffle_playlist) return a
preview on the first call and only act when repeated with confirm=true -
show the preview to the user before confirming."""


def build_server() -> FastMCP:
    app = FastMCP("spotify", instructions=INSTRUCTIONS)
    for tool in ALL_TOOLS:
        capability = CAPABILITIES[tool.__name__]
        app.tool(
            annotations=ToolAnnotations(
                readOnlyHint=capability.read_only,
                destructiveHint=capability.destructive,
                idempotentHint=capability.idempotent,
                openWorldHint=True,  # every tool talks to the Spotify Web API
            )
        )(tool)
    return app


def main(verbosity: int = 1) -> None:
    configure_logging(verbosity)  # stderr only; stdout is the protocol channel
    build_server().run()


if __name__ == "__main__":
    main()
