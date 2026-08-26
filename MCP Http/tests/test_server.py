"""V1 contract: the server lists documents and refuses to serve their content."""

from __future__ import annotations

import pytest
from mcp.server.mcpserver.exceptions import ResourceError

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
    assert "V1" in message
    assert resource.uri in message


@pytest.mark.anyio
async def test_server_exposes_no_tools(entries):
    server = build_server(entries)
    assert await server.list_tools() == []


@pytest.mark.anyio
async def test_server_lists_every_document(entries):
    server = build_server(entries)
    assert len(await server.list_resources()) == len(entries)


@pytest.fixture
def anyio_backend():
    return "asyncio"
