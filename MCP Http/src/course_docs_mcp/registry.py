"""Static, validated registry of public course documents.

The registry stores Google *document IDs*, never full URLs. Export URLs are
derived here, in code, so a hand-edited config file cannot point the server at
an arbitrary host. This is the spec's "prefer a hardcoded allowlist of document
IDs over accepting arbitrary Google Docs URLs" rule, enforced structurally.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DOCS_EXPORT_URL = "https://docs.google.com/document/d/{doc_id}/export?format={fmt}"
DRIVE_DOWNLOAD_URL = "https://drive.google.com/uc?export=download&id={doc_id}"

FORMAT_MIME_TYPES = {"md": "text/markdown", "txt": "text/plain"}


class DocEntry(BaseModel):
    """One allowlisted course document."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    doc_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")

    kind: Literal["google_doc", "drive_file"] = "google_doc"
    # google_doc only: which Google export format to request.
    format: Literal["md", "txt"] | None = None
    # drive_file only: the file's own type, since Drive files are not converted.
    mime_type: str | None = None

    # Descriptive metadata returned by list_course_documents.
    week_scope: str | None = None
    source_role: str | None = None

    @model_validator(mode="after")
    def _check_kind_fields(self) -> DocEntry:
        if self.kind == "google_doc":
            if self.mime_type is not None:
                raise ValueError(
                    f"{self.name}: 'mime_type' is derived from 'format' for a google_doc; remove it"
                )
            if self.format is None:
                raise ValueError(f"{self.name}: a google_doc requires 'format' ('md' or 'txt')")
        else:
            if self.format is not None:
                raise ValueError(
                    f"{self.name}: a drive_file is not converted, so 'format' does not apply"
                )
            if not self.mime_type:
                raise ValueError(f"{self.name}: a drive_file requires an explicit 'mime_type'")
        return self

    @property
    def uri(self) -> str:
        """The public URL a client fetches to get this document's content."""
        if self.kind == "google_doc":
            return DOCS_EXPORT_URL.format(doc_id=self.doc_id, fmt=self.format)
        return DRIVE_DOWNLOAD_URL.format(doc_id=self.doc_id)

    @property
    def resource_mime_type(self) -> str:
        """The MIME type advertised to MCP clients."""
        if self.kind == "google_doc":
            return FORMAT_MIME_TYPES[self.format]  # type: ignore[index]
        return self.mime_type  # type: ignore[return-value]


def load_registry(path: str | Path) -> list[DocEntry]:
    """Load and validate the document registry, failing fast on any problem.

    A bad registry should stop the server at startup, not surface as a confusing
    empty resource list mid-demo.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Document registry not found: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"{path}: expected a JSON array of document entries")

    entries = [DocEntry.model_validate(item) for item in raw]

    seen: set[str] = set()
    for entry in entries:
        if entry.name in seen:
            raise ValueError(f"{path}: duplicate resource name {entry.name!r}")
        seen.add(entry.name)

    if not entries:
        raise ValueError(f"{path}: registry is empty; the server would expose no resources")

    return entries
