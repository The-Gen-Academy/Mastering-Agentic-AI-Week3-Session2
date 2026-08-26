"""Read-only Streamable HTTP MCP server exposing public course documents."""

from .registry import DocEntry, load_registry
from .server import build_server

__all__ = ["DocEntry", "load_registry", "build_server"]
