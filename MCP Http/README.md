# Course Docs MCP Server

A read-only [Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)
MCP server that exposes a curated set of public course documents as
[MCP resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources).

No auth, no write tools, no document processing. The server is a **directory**: it tells
clients which documents exist and where to fetch them. Clients fetch and process the
content themselves.

## Quick start

```bash
uv sync
uv run python -m course_docs_mcp          # http://127.0.0.1:8000/mcp
```

In another terminal:

```bash
uv run python scripts/smoke.py            # connect, list resources, verify the contract
```

Or point the MCP Inspector at it:

```bash
npx @modelcontextprotocol/inspector
```

### Connect from Claude Code

```bash
claude mcp add --transport http course-docs http://127.0.0.1:8000/mcp
```

## What it exposes

`resources/list` returns five documents:

| name | title | type |
|---|---|---|
| `cohort-faq` | Mastering Agentic AI Cohort FAQ | `application/pdf` |
| `onboarding-guidebook` | August 2026 Onboarding Guidebook | `text/markdown` |
| `week-1-project-handout` | Week 1 Project Handout | `text/markdown` |
| `week-2-rag-project-handout` | Week 2 RAG Project Handout | `text/markdown` |
| `week-3-agent-project-handout` | Week 3 Agent Project Handout | `text/markdown` |

## Client responsibilities (V1)

This server does **not** serve document content. A client is expected to:

1. Connect and call `resources/list`.
2. Fetch each resource's `uri` directly over HTTPS.
3. Chunk, embed, summarize, or search the content locally.
4. Preserve attribution using each resource's `title` and `uri`.

Calling `resources/read` returns an explanatory error pointing at the URI to fetch,
rather than a bare protocol error.

### Two things that will bite you when fetching

- **Google returns `text/x-markdown`**, not the `text/markdown` this server advertises.
  Match loosely if you branch on content type.
- **A doc that is not public returns an HTML sign-in page, often with HTTP 200.** Your
  fetcher should treat an unexpected `text/html` response as a failure, or you will
  silently feed a Google login page to a model as course content.

## Configuration

Documents live in `docs.config.json`. The registry stores **document IDs, never URLs** —
export URLs are derived in code, so a hand-edited config cannot point the server at an
arbitrary host. Add a Google Doc with:

```json
{
  "name": "week-4-project-handout",
  "title": "Week 4 Project Handout",
  "description": "Week 4 project: requirements, deliverables, and submission logistics.",
  "kind": "google_doc",
  "doc_id": "PASTE_THE_ID_FROM_THE_DOC_URL",
  "format": "md",
  "week_scope": "week_4",
  "source_role": "weekly_project_logistics"
}
```

The doc ID is the segment between `/d/` and `/edit` in the document's URL. The document
must be shared so that **anyone with the link can view** it. `week_scope` and
`source_role` are descriptive only — they are not sent over the wire in V1.

The registry is validated at startup and a bad entry stops the server immediately,
rather than surfacing as a confusing empty resource list mid-session.

Environment variables (see `.env.example`): `HOST`, `PORT`, `MCP_PATH`, `DOCS_CONFIG`.

## Layout

```
docs.config.json            the allowlist
src/course_docs_mcp/
  registry.py               validation + doc_id -> export URL
  server.py                 MCP server and resource definitions
  __main__.py               entry point
scripts/smoke.py            end-to-end client check
tests/                      registry and contract tests
```

## Tests

```bash
uv run pytest
```

## Notes

- **Transport is stateless.** Every POST gets a fresh transport; nothing here needs
  server-push, so there is no session to track and no SSE or DELETE route.
- **The FAQ is a PDF, not a Google Doc**, so it has no `export?format=md` link and is
  listed with its Drive download URL and `application/pdf`. Converting it to a Google
  Doc (open in Drive → *Open with Google Docs*) would make the registry homogeneous;
  swap in the new ID and set `"kind": "google_doc", "format": "md"`.
- **Treat document contents as untrusted input**, even though they are authored
  internally. Resource descriptions are prompt-visible and are kept factual and minimal.

## Not implemented (by design)

`resources/read` serving content, search tools, participant auth, Google OAuth,
document editing, private Drive access, and any server-side vector store.
