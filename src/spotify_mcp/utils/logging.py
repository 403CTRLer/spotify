import logging
import sys

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(verbosity: int = 0) -> None:
    """Route all spotify_mcp logs to stderr (stdout is the MCP transport).

    verbosity: 0 = WARNING, 1 = INFO, 2+ = DEBUG.
    """
    level = logging.DEBUG if verbosity >= 2 else logging.INFO if verbosity == 1 else logging.WARNING
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT))
    root = logging.getLogger("spotify_mcp")
    root.setLevel(level)
    root.handlers[:] = [handler]
