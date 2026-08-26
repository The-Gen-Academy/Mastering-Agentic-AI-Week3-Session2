"""Builds the read-only MCP server that exposes the course document registry."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError
from mcp.server.mcpserver.resources import Resource

from .registry import DocEntry

INSTRUCTIONS = """\
Read-only directory of public course documents for the Mastering Agentic AI cohort.

Call resources/list to discover the available documents, then fetch each resource's
URI directly over HTTPS to obtain its content. This server does not serve document
content itself. Preserve source attribution using each resource's title and URI.
"""


class CourseDocResource(Resource):
    """A course document, exposed as a listing entry only.

    In V1 the server is a directory, not a proxy: it advertises where each document
    lives and the client fetches it. `read()` therefore refuses with an explanatory
    message rather than a bare protocol error, so a client that assumes
    resources/read learns why nothing came back.
    """

    async def read(self) -> str | bytes:
        raise ResourceError(
            f"This server does not serve document content (V1: resources/list only). "
            f"Fetch {self.uri} directly over HTTPS to read {self.name!r}."
        )


def build_resources(entries: list[DocEntry]) -> list[Resource]:
    """Turn validated registry entries into MCP resources."""
    return [
        CourseDocResource(
            uri=entry.uri,
            name=entry.name,
            title=entry.title,
            description=entry.description,
            mime_type=entry.resource_mime_type,
        )
        for entry in entries
    ]


def build_server(entries: list[DocEntry]) -> MCPServer:
    """Construct the MCP server for a validated registry."""
    return MCPServer(
        name="course-docs",
        title="Course Documents",
        instructions=INSTRUCTIONS,
        version="0.1.0",
        resources=build_resources(entries),
    )
