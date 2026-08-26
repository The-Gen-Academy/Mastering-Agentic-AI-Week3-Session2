"""Entry point: load the registry, then serve it over Streamable HTTP."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from .registry import load_registry
from .server import build_server

DEFAULT_CONFIG = "docs.config.json"

logger = logging.getLogger("course_docs_mcp")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    config_path = Path(os.environ.get("DOCS_CONFIG", DEFAULT_CONFIG))
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    mcp_path = os.environ.get("MCP_PATH", "/mcp")

    try:
        entries = load_registry(config_path)
    except Exception as exc:
        # Fail loudly at startup rather than serving an empty or wrong resource list.
        logger.error("Could not load %s: %s", config_path, exc)
        return 1

    logger.info("Loaded %d documents from %s", len(entries), config_path)
    for entry in entries:
        logger.info("  %s -> %s", entry.name, entry.uri)

    server = build_server(entries)
    logger.info("Serving MCP over Streamable HTTP at http://%s:%d%s", host, port, mcp_path)

    # Stateless: every POST gets a fresh transport. Nothing here needs server-push,
    # so there is no session state to track and no GET/SSE or DELETE route to serve.
    server.run(
        transport="streamable-http",
        host=host,
        port=port,
        streamable_http_path=mcp_path,
        stateless_http=True,
        json_response=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
