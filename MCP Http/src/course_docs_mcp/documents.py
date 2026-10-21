"""Fetch text from the public Google documents in the registry."""

from __future__ import annotations

import asyncio

import httpx2

from .registry import DocEntry

MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
TEXT_TYPES = {"text/plain", "text/markdown", "text/x-markdown"}


def _check_url(url: httpx2.URL) -> None:
    host = url.host
    if url.scheme != "https" or url.port not in (None, 443) or not (
        host == "docs.google.com"
        or host == "googleusercontent.com"
        or host.endswith(".googleusercontent.com")
    ):
        raise ValueError("Document download redirected outside the allowed Google export hosts.")


async def _download(entry: DocEntry) -> str:
    url = httpx2.URL(entry.uri)
    async with httpx2.AsyncClient(timeout=15, follow_redirects=False) as client:
        for _ in range(6):
            _check_url(url)
            async with client.stream("GET", url) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("Document download returned a redirect without a location.")
                    url = response.url.join(location)
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
                if content_type not in TEXT_TYPES:
                    raise ValueError(
                        "Document download did not return Markdown or plain text. "
                        "Check that the document is shared with anyone who has the link."
                    )
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_DOCUMENT_BYTES:
                        raise ValueError("Document exceeds the 2 MiB download limit.")
                text = content.decode("utf-8-sig")
                if not text.strip():
                    raise ValueError("Document download returned empty content.")
                if text.lstrip().lower().startswith(("<!doctype html", "<html")):
                    raise ValueError("Document download returned an HTML page instead of course content.")
                return text
    raise ValueError("Document download exceeded the redirect limit.")


async def fetch_document(entry: DocEntry) -> str:
    """Download a registered Google Doc with bounded time, size, and redirects."""
    if entry.kind != "google_doc":
        raise ValueError("Reading is supported only for Google Docs exported as Markdown or text.")
    try:
        return await asyncio.wait_for(_download(entry), timeout=30)
    except (TimeoutError, httpx2.TimeoutException) as exc:
        raise ValueError("Document download timed out. Try again shortly.") from exc
    except httpx2.HTTPStatusError as exc:
        raise ValueError(
            f"Document download failed with HTTP {exc.response.status_code}. "
            "Check that the document exists and is publicly readable."
        ) from exc
    except httpx2.RequestError as exc:
        raise ValueError("Could not reach Google to download the document. Try again shortly.") from exc
    except UnicodeDecodeError as exc:
        raise ValueError("Document download was not valid UTF-8 text.") from exc
