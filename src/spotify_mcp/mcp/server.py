from mcp.server.fastmcp import FastMCP

from spotify_mcp.tools.definitions import ALL_TOOLS
from spotify_mcp.utils.logging import configure_logging


def build_server() -> FastMCP:
    app = FastMCP("spotify")
    for tool in ALL_TOOLS:
        app.tool()(tool)
    return app


def main() -> None:
    configure_logging(1)  # INFO to stderr; stdout is the protocol channel
    build_server().run()


if __name__ == "__main__":
    main()
