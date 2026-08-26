"""The registry is the security boundary, so its rejections are the tests that matter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from course_docs_mcp.registry import DocEntry, load_registry

REAL_CONFIG = Path(__file__).resolve().parent.parent / "docs.config.json"

GOOD_DOC = {
    "name": "week-1-project-handout",
    "title": "Week 1 Project Handout",
    "description": "Week 1 project requirements and logistics.",
    "kind": "google_doc",
    "doc_id": "1CBqSbFnyb84NdYcIgQJk72ZgdjY0t97e6fTDru5uqJI",
    "format": "md",
}
GOOD_FILE = {
    "name": "cohort-faq",
    "title": "Cohort FAQ",
    "description": "Frequently asked questions.",
    "kind": "drive_file",
    "doc_id": "1jfWqpSmsoZmkDOcCRw0WOZw3f9rBvxaf",
    "mime_type": "application/pdf",
}


def write(tmp_path: Path, data: object) -> Path:
    path = tmp_path / "docs.config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_shipped_registry_is_valid():
    entries = load_registry(REAL_CONFIG)
    assert len(entries) == 5
    assert len({e.name for e in entries}) == 5


def test_google_doc_uri_is_a_markdown_export_link():
    entry = DocEntry.model_validate(GOOD_DOC)
    assert entry.uri == (
        "https://docs.google.com/document/d/"
        "1CBqSbFnyb84NdYcIgQJk72ZgdjY0t97e6fTDru5uqJI/export?format=md"
    )
    assert entry.resource_mime_type == "text/markdown"
    assert "/edit" not in entry.uri and "/view" not in entry.uri


def test_drive_file_uri_and_declared_mime_type():
    entry = DocEntry.model_validate(GOOD_FILE)
    assert entry.uri.startswith("https://drive.google.com/uc?export=download&id=")
    assert entry.resource_mime_type == "application/pdf"


def test_txt_format_maps_to_plain_text():
    entry = DocEntry.model_validate({**GOOD_DOC, "format": "txt"})
    assert entry.uri.endswith("?format=txt")
    assert entry.resource_mime_type == "text/plain"


@pytest.mark.parametrize(
    "label, mutation",
    [
        # The allowlist rule: only an ID may be configured, never a URL or a host.
        ("url smuggled into doc_id", {"doc_id": "evil.example.com/x?a=b"}),
        ("path smuggled into doc_id", {"doc_id": "abc/../../etc/passwd"}),
        ("name must be a slug", {"name": "Week_1"}),
        ("google_doc needs a format", {"format": None}),
        ("google_doc cannot override mime_type", {"mime_type": "text/html"}),
        ("unknown fields are typos", {"sneaky": 1}),
        ("title cannot be blank", {"title": ""}),
        ("description cannot be blank", {"description": ""}),
    ],
)
def test_rejects_bad_entry(label, mutation):
    with pytest.raises(Exception):
        DocEntry.model_validate({**GOOD_DOC, **mutation})


def test_drive_file_requires_mime_type():
    with pytest.raises(Exception):
        DocEntry.model_validate({k: v for k, v in GOOD_FILE.items() if k != "mime_type"})


def test_drive_file_rejects_format():
    with pytest.raises(Exception):
        DocEntry.model_validate({**GOOD_FILE, "format": "md"})


def test_rejects_duplicate_names(tmp_path):
    path = write(tmp_path, [GOOD_DOC, {**GOOD_DOC, "title": "Copy"}])
    with pytest.raises(ValueError, match="duplicate resource name"):
        load_registry(path)


def test_rejects_empty_registry(tmp_path):
    with pytest.raises(ValueError, match="empty"):
        load_registry(write(tmp_path, []))


def test_rejects_non_list(tmp_path):
    with pytest.raises(ValueError, match="expected a JSON array"):
        load_registry(write(tmp_path, {"name": "x"}))


def test_missing_file_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_registry(tmp_path / "absent.json")
