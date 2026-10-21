"""Verify discovery and read every registered handout over the running MCP server.

Usage: uv run python scripts/smoke.py [url]
This check fetches live public documents from Google through the read tool.
"""

from __future__ import annotations

import asyncio
import sys

from mcp import Client, MCPError

DEFAULT_URL = "http://127.0.0.1:8000/mcp"
EXPECTED_PROTOCOL = "2026-07-28"
EXPECTED_TOOLS = {"list_course_documents", "read_course_document"}
EXPECTED_DOCUMENTS = {
    "week-1-project-handout", "week-2-rag-project-handout", "week-3-agent-project-handout",
}


async def main(url: str) -> int:
    async with Client(url) as client:
        info = client.server_info
        if info is None:
            raise ValueError("Server did not report its identity")
        print(f"connected to {info.name} v{info.version} ({url})")
        if client.protocol_version != EXPECTED_PROTOCOL:
            raise ValueError(f"Expected MCP {EXPECTED_PROTOCOL}, got {client.protocol_version}")
        resources = client.server_capabilities.resources
        if resources is None or resources.subscribe or resources.list_changed:
            raise ValueError("Expected static resources without subscriptions")

        tools = (await client.list_tools()).tools
        if {t.name for t in tools} != EXPECTED_TOOLS:
            raise ValueError("Expected list_course_documents and read_course_document; restart the server")
        if not all(t.annotations and t.annotations.read_only_hint for t in tools):
            raise ValueError("Both tools must be annotated as read-only")
        print(f"tools/list -> {len(tools)} read-only tools")

        listed = (await client.list_resources()).resources
        catalog = await client.call_tool("list_course_documents", {})
        if catalog.is_error or not catalog.structured_content:
            raise ValueError(f"Could not list documents: {catalog.content}")
        documents = catalog.structured_content["result"]
        if len(documents) != 3 or {d["name"] for d in documents} != EXPECTED_DOCUMENTS:
            raise ValueError("Expected only the three project handouts")
        if {(r.name, r.uri) for r in listed} != {(d["name"], d["url"]) for d in documents}:
            raise ValueError("Resource directory and document tool disagree")
        print(f"resources/list and list_course_documents -> {len(documents)} handouts")

        for document in documents:
            result = await client.call_tool("read_course_document", {"name": document["name"]})
            if result.is_error or not result.structured_content:
                raise ValueError(f"Could not read {document['name']}: {result.content}")
            data = result.structured_content
            if not data["content"].strip() or data["url"] != document["url"] or data["title"] != document["title"]:
                raise ValueError(f"Missing content or attribution for {document['name']}")
            print(f"  read {document['name']}: {len(data['content'])} characters, source attribution present")

        invalid = await client.call_tool("read_course_document", {"name": "onboarding-guidebook"})
        if not invalid.is_error or "Unknown document name" not in invalid.content[0].text:
            raise ValueError("Removed documents must not be readable")

        probe = listed[0]
        try:
            await client.read_resource(probe.uri)
        except MCPError as exc:
            if "read_course_document" not in exc.error.message or probe.uri not in exc.error.message:
                raise ValueError(f"Unexpected resources/read error: {exc}") from exc
        else:
            raise ValueError("Resources should retain the directory-only interface")
        print("OK")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL)))
