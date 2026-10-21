"""Exercise downloads without depending on Google availability."""

import httpx2
import pytest

from course_docs_mcp.documents import fetch_document
from course_docs_mcp.registry import DocEntry
from tests.test_registry import GOOD_DOC


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mock_google(monkeypatch):
    original_client = httpx2.AsyncClient

    def install(handler):
        monkeypatch.setattr(
            "course_docs_mcp.documents.httpx2.AsyncClient",
            lambda **kwargs: original_client(transport=httpx2.MockTransport(handler), **kwargs),
        )

    return install


@pytest.mark.anyio
async def test_reads_google_markdown_after_allowed_redirect(mock_google):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if request.url.host == "docs.google.com":
            return httpx2.Response(302, headers={"location": "https://doc-1.googleusercontent.com/export"})
        return httpx2.Response(
            200, headers={"content-type": "text/x-markdown; charset=utf-8"},
            content=b"\xef\xbb\xbf# Project\nComplete the assignment.",
        )

    mock_google(handler)
    assert await fetch_document(DocEntry(**GOOD_DOC)) == "# Project\nComplete the assignment."
    assert len(calls) == 2


@pytest.mark.anyio
@pytest.mark.parametrize(
    "target",
    ["https://accounts.google.com/login", "http://docs.google.com/export",
     "https://googleusercontent.com.evil.example/export", "http://127.0.0.1/secret"],
)
async def test_rejects_redirect_before_contacting_unapproved_host(mock_google, target):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx2.Response(302, headers={"location": target})

    mock_google(handler)
    with pytest.raises(ValueError, match="allowed Google"):
        await fetch_document(DocEntry(**GOOD_DOC))
    assert len(calls) == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "status, content_type, body, message",
    [
        (403, "text/plain", b"Forbidden", "HTTP 403"),
        (200, "text/html", b"<html>Sign in</html>", "Markdown or plain text"),
        (200, "text/plain", b"<!DOCTYPE html><html>Sign in</html>", "HTML page"),
        (200, "text/plain", b"   ", "empty"),
        (200, "text/plain", b"x" * (2 * 1024 * 1024 + 1), "2 MiB"),
        (200, "text/plain", b"\xff", "UTF-8"),
    ],
)
async def test_download_errors(mock_google, status, content_type, body, message):
    mock_google(lambda request: httpx2.Response(
        status, headers={"content-type": content_type}, content=body,
    ))
    with pytest.raises(ValueError, match=message):
        await fetch_document(DocEntry(**GOOD_DOC))


@pytest.mark.anyio
async def test_timeout_has_useful_message(mock_google):
    def handler(request):
        raise httpx2.ReadTimeout("slow", request=request)

    mock_google(handler)
    with pytest.raises(ValueError, match="timed out"):
        await fetch_document(DocEntry(**GOOD_DOC))
