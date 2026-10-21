"""Exercise JSON-RPC over HTTP for current and legacy MCP clients."""

from __future__ import annotations

import json

import httpx2
import pytest
from mcp import Client, MCPError
from mcp.client.streamable_http import streamable_http_client

from course_docs_mcp.registry import load_registry
from course_docs_mcp.server import build_server
from tests.test_registry import REAL_CONFIG


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("mode", "expected_protocol"),
    [("auto", "2026-07-28"), ("legacy", "2025-11-25")],
)
async def test_directory_contract_over_http(mode, expected_protocol, monkeypatch):
    entries = load_registry(REAL_CONFIG)
    async def fetch_document(entry):
        if entry == entries[0]:
            raise ValueError("Document download timed out. Try again shortly.")
        assert entry == entries[2]
        return "# Week 3\nProject requirements."

    monkeypatch.setattr("course_docs_mcp.server.fetch_document", fetch_document)
    server = build_server(entries)
    app = server.streamable_http_app(stateless_http=True, json_response=True)
    requests = []
    responses = []

    async def record_request(request):
        if request.method == "POST":
            requests.append(json.loads(request.content))

    async def record_response(response):
        responses.append(response)

    async with app.router.lifespan_context(app):
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            event_hooks={"request": [record_request], "response": [record_response]},
        ) as http:
            transport = streamable_http_client("http://127.0.0.1:8000/mcp", http_client=http)
            async with Client(transport, mode=mode) as client:
                assert client.protocol_version == expected_protocol
                assert client.server_info.name == "course-docs"
                resources = client.server_capabilities.resources
                assert resources is not None
                assert not resources.subscribe
                assert not resources.list_changed
                tools = (await client.list_tools()).tools
                assert {t.name for t in tools} == {"list_course_documents", "read_course_document"}
                catalog = await client.call_tool("list_course_documents", {})
                assert not catalog.is_error
                documents = catalog.structured_content["result"]
                assert [d["name"] for d in documents] == [e.name for e in entries]
                assert documents[2]["week_scope"] == "week_3"
                assert documents[2]["url"] == entries[2].uri
                read = await client.call_tool("read_course_document", {"name": entries[2].name})
                assert not read.is_error
                assert read.structured_content == {
                    "name": entries[2].name,
                    "title": entries[2].title,
                    "url": entries[2].uri,
                    "mime_type": "text/markdown",
                    "content": "# Week 3\nProject requirements.",
                }
                for name, message in [
                    ("onboarding-guidebook", "Unknown document name"),
                    (entries[0].name, "Document download timed out"),
                ]:
                    error = await client.call_tool("read_course_document", {"name": name})
                    assert error.is_error
                    assert message in error.content[0].text
                listed = (await client.list_resources()).resources
                assert [
                    (r.uri, r.name, r.title, r.description, r.mime_type) for r in listed
                ] == [
                    (e.uri, e.name, e.title, e.description, e.resource_mime_type) for e in entries
                ]
                with pytest.raises(MCPError) as exc:
                    await client.read_resource(entries[0].uri)
                assert "read_course_document" in exc.value.error.message
                assert entries[0].uri in exc.value.error.message

            # Modern MCP rejects GET; both paths have no session to terminate.
            for method in (("GET", "DELETE") if mode == "auto" else ("DELETE",)):
                response = await http.request(
                    method,
                    "http://127.0.0.1:8000/mcp",
                    headers={"MCP-Protocol-Version": expected_protocol},
                )
                assert response.status_code == 405

    assert all("mcp-session-id" not in response.headers for response in responses)
    methods = [request["method"] for request in requests]
    if mode == "auto":
        assert "server/discover" in methods
        assert "initialize" not in methods
        assert "notifications/initialized" not in methods
        listing = next(r for r in requests if r["method"] == "resources/list")
        assert (
            listing["params"]["_meta"]["io.modelcontextprotocol/protocolVersion"]
            == expected_protocol
        )
    else:
        assert "initialize" in methods
        assert "notifications/initialized" in methods
