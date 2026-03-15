# File: __main__.py
# Description: Entrypoint for python -m ultrahuman_mcp (stdio MCP server).
# Created: 2026-03-16
# Last updated: 2026-03-15

from .log_config import configure_logging
from .server import mcp

if __name__ == "__main__":
    configure_logging()
    mcp.run()
