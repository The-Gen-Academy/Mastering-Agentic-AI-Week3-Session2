"""Resources retain their directory interface; tools list and read handouts."""

from __future__ import annotations

import pytest
from mcp.server.mcpserver.exceptions import ResourceError, ToolError

from course_docs_mcp.registry import load_registry
from course_docs_mcp.server import build_resources, build_server
from tests.test_registry import REAL_CONFIG


@pytest.fixture
def entries():
    return load_registry(REAL_CONFIG)


def test_every_entry_becomes_a_resource(entries):
    resources = build_resources(entries)
    assert len(resources) == len(entries)
    for resource, entry in zip(resources, entries):
        assert resource.uri == entry.uri
        assert resource.name == entry.name
        assert resource.title == entry.title
        assert resource.mime_type == entry.resource_mime_type


def test_no_resource_uses_an_edit_or_view_link(entries):
    for resource in build_resources(entries):
        assert "/edit" not in resource.uri
        assert "/view" not in resource.uri


@pytest.mark.anyio
async def test_read_refuses_with_an_explanation(entries):
    resource = build_resources(entries)[0]
    with pytest.raises(ResourceError) as excinfo:
        await resource.read()
    message = str(excinfo.value)
    assert "read_course_document" in message
    assert resource.uri in message


@pytest.mark.anyio
async def test_server_exposes_read_only_tools(entries):
    server = build_server(entries)
    tools = await server.list_tools()
    assert {t.name for t in tools} == {"list_course_documents", "read_course_document"}
    assert all(t.annotations.read_only_hint for t in tools)


@pytest.mark.anyio
@pytest.mark.parametrize("name", ["cohort-faq", "onboarding-guidebook", "https://example.com", "../secret"])
async def test_read_rejects_unknown_names_without_fetching(entries, monkeypatch, name):
    async def unexpected_fetch(entry):
        pytest.fail("Unknown document must not trigger a network request")

    monkeypatch.setattr("course_docs_mcp.server.fetch_document", unexpected_fetch)
    with pytest.raises(ToolError, match="Unknown document name"):
        await build_server(entries).call_tool("read_course_document", {"name": name})


@pytest.mark.anyio
async def test_server_lists_every_document(entries):
    server = build_server(entries)
    assert len(await server.list_resources()) == len(entries)


@pytest.fixture
def anyio_backend():
    return "asyncio"
