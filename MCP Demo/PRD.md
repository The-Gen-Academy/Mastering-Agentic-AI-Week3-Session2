# PRD — MCP Tutorial: Course Platform Demo

**Status:** Draft v1
**Owner:** Arvind
**Last updated:** 2026-06-11

---

## 1. Purpose

Build a miniature course-platform application (a "mini Maven") that serves as the vehicle for a tutorial demonstrating the value of **MCP (Model Context Protocol)**. The tutorial shows how an AI client (Claude Code) can agentically read and modify a real application through a local MCP server — and, critically, how a well-designed MCP layer is oriented around **human intent** rather than mirroring the underlying CRUD API.

Everything runs locally: frontend, backend, and MCP server.

### Tutorial thesis (the one-picture takeaway)

> Same backend, two consumers: the React UI speaks raw CRUD; Claude speaks intent through the MCP layer. A single JSON file is the source of truth both converge on.

---

## 2. Goals & Non-Goals

### Goals

1. A working, locally-runnable course platform with a two-week curriculum view (dates, sessions, resources).
2. A REST API over a file-backed mock database.
3. A Python MCP server exposing a **small, intent-oriented toolset** (4 tools) — explicitly *not* a 1:1 mapping of the API.
4. Connect the MCP server to Claude Code via stdio (`.mcp.json` checked into the repo).
5. Support two headline demo moments:
   - **Fetch:** "Get me the slides link for the NVIDIA guest lecture."
   - **Publish:** "The recording for Live Session 1 is up — here's the URL." (React UI visibly updates.)
6. Teach key MCP design lessons: fuzzy human-reference resolution, formatted summaries over raw JSON, domain-rule-guarded writes, conversational error messages, intent composition.

### Non-Goals

- **No authentication or authorization.** All endpoints open; all users can perform all actions.
- **No real database.** Local JSON file only.
- **No file uploads/storage.** Resources are links or inline text placeholders only.
- **No multi-user, no realtime infra** (simple polling is fine), no deployment story.
- The course platform itself is deliberately minimal — it must not outgrow its role as the demo vehicle.

---

## 3. Personas

| Persona | Role in demo | Example intents |
|---|---|---|
| **Student** | Consumes the course | "What's happening this week?", "Get me the slides for X", "What should I focus on?" |
| **Instructor** | Maintains the course | "Publish last night's recording", "Fix this broken link" |

Both personas interact through Claude Code in the demo; the React UI is the always-visible proof that changes really happened.

---

## 4. System Architecture

```
React (Vite, :5173) ──HTTP GET──▶ FastAPI (:8000) ◀──HTTP── MCP Server (Python/FastMCP)
                                      │                          ▲
                                data/curriculum.json             │ stdio (JSON-RPC)
                                (mock database)             Claude Code
```

- **One writer path:** only the FastAPI backend touches the JSON file (atomic writes: temp file + rename). The MCP server and frontend both go through the API — no file-lock contention.
- **MCP transport:** stdio. Claude Code launches the MCP server as a subprocess via `.mcp.json` — no port, no lifecycle management.
- **Live updates:** the React app polls the API (every ~2s) so MCP-driven changes appear on screen without a manual refresh.

---

## 5. Data Model

Single file: `data/curriculum.json`.

```
Course
 └─ weeks[]                 Week
     ├─ number, title, date_range
     └─ items[]             Item
         ├─ id              e.g. "itm_003"
         ├─ title           e.g. "Live Session 1 - Week 2"
         ├─ type            live_session | office_hours | guest_lecture |
         │                  topic_group | project | reading
         ├─ date            ISO date
         ├─ start_time / end_time / timezone
         ├─ optional        boolean
         ├─ completed       boolean (drives progress display)
         └─ resources[]     Resource
             ├─ id          e.g. "res_01"
             ├─ label       "Recording" | "Slides" | ...
             ├─ kind        link | text
             └─ url | text  (by kind; placeholders allowed)
```

Seed data mirrors a realistic Week 1 + Week 2 curriculum (live sessions, office hours, optional guest lectures, topic groups, a weekly project), modeled on the Maven-style layout.

---

## 6. REST API (FastAPI, port 8000)

Resource-oriented CRUD — deliberately plain, because the contrast with the MCP layer is the teaching point. **No auth on any endpoint.**

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/curriculum` | Full course tree |
| GET | `/weeks/{n}` | One week with items |
| GET | `/items/{id}` | One item with resources |
| GET | `/items?week=&type=&date=` | Filtered listing |
| PATCH | `/items/{id}` | Update item fields (title, date, times, optional, completed) |
| POST | `/items/{id}/resources` | Add a resource |
| PATCH | `/items/{id}/resources/{rid}` | Update a resource (label, url, text) |
| DELETE | `/items/{id}/resources/{rid}` | Remove a resource |

Implementation notes:
- Pydantic models for Course / Week / Item / Resource.
- Atomic JSON writes (write temp, rename).
- CORS open for the local frontend.
- FastAPI's auto-generated `/docs` page is used in the tutorial ("here's the API").

---

## 7. MCP Server (Python, FastMCP, stdio)

### Design principles

1. **Intent over endpoints.** Tools are named for sentences humans actually say. Test: would the tool name plausibly appear in the user's own words?
2. **Human references, not IDs.** Tools accept names like "the NVIDIA lecture"; the server fuzzy-matches titles and returns a disambiguation list when ambiguous.
3. **Formatted summaries, not raw JSON.** Read tools return compact markdown digests — cheaper in tokens, more useful to every client.
4. **Domain rules live in the tool.** Writes validate invariants the API doesn't know about (e.g., recordings only attach to sessions that already happened).
5. **Conversational errors.** Tool error strings go straight into the model's context — well-written errors let *any* client recover gracefully.
6. **Portability.** Intent tools matter *more* for less-capable MCP clients: composition ability varies across clients, so logic baked into the tool yields a consistent experience everywhere.

### Toolset (exactly 4 tools)

| # | Tool | Type | Intent served | Internal behavior |
|---|---|---|---|---|
| 1 | `get_schedule(week?)` | Read | "Show me what's happening in Week 2" | Filtered GET → chronological digest with dates, times, optional flags |
| 2 | `get_session_details(session)` | Read | "Get me the slides link for the NVIDIA lecture" | Fuzzy-resolve name → GET item → timing + all resources with URLs |
| 3 | `publish_recording(session, recording_url)` | Write | "The recording for Live Session 1 is up" | Resolve name → validate session date is in the past → replace existing "Recording" placeholder if present, else add → confirm. Friendly refusal if session hasn't happened. |
| 4 | `whats_next()` | Read | "What should I focus on?" | Joins today's date + schedule + completion state; separates required from optional; flags past-due items. **No single API endpoint corresponds to this.** |

### Explicitly cut (tutorial "exercises for the reader")

`audit_course()`, `shift_schedule(scope, delta)`, `catch_up(since)`, generic `add_resource` / `mark_complete` / `find_session` (name resolution is internal plumbing, not a tool).

### Claude Code integration

`.mcp.json` at repo root so anyone cloning the project gets the server automatically:

```json
{
  "mcpServers": {
    "course-platform": {
      "command": "uv",
      "args": ["run", "mcp_server.py"]
    }
  }
}
```

---

## 8. Frontend (React + Vite, port 5173)

**Read-only viewer** — its job is to prove Claude's writes happened.

- Week-by-week curriculum view styled loosely after the Maven layout: date chips, session cards, time ranges, OPTIONAL tags, resource buttons (Recording / Slides), progress rings per topic group.
- Resource buttons link out; placeholder resources render visibly as placeholders (so "publishing" a recording is a visible state change).
- Polls the API every ~2 seconds for live updates during demos.
- No edit forms. (Optional stretch: a "completed" checkbox to feed `whats_next()` demos.)

---

## 9. Demo Script (tutorial arc)

1. **Tour the app** in the browser — "here's our course platform."
2. **Show the API** via FastAPI `/docs` — "here's its plain CRUD surface."
3. **Build the MCP server** — the meat of the tutorial (~100 lines). Walk through the intent-layer design principles.
4. **Connect Claude Code** — `.mcp.json`, then `/mcp` to show the connected tools.
5. **Demo 1 (fetch):** "Get me the slides link for the NVIDIA guest lecture" → fuzzy resolution + formatted answer.
6. **Demo 2 (publish):** "The recording for Live Session 1 is up: ⟨url⟩" → domain validation, placeholder replacement, **React UI updates on screen**.
7. **Demo 3 (guard rail):** Try publishing a recording to a *future* session → conversational refusal.
8. **Demo 4 (intent showcase):** "What should I focus on?" → `whats_next()` composes an answer no endpoint provides.
9. **Closing lesson:** API-vs-MCP comparison table; why intent beats 1:1 mapping; cut tools as reader exercises.

---

## 10. Project Structure (proposed)

```
MCP Demo/
├── PRD.md
├── .mcp.json                  # Claude Code MCP registration
├── data/
│   └── curriculum.json        # mock database (seeded)
├── backend/
│   ├── main.py                # FastAPI app + routes
│   ├── models.py              # Pydantic models
│   └── storage.py             # atomic JSON read/write
├── mcp_server/
│   └── mcp_server.py          # FastMCP server (4 tools + name resolution)
└── frontend/
    └── (Vite + React app)     # read-only curriculum viewer
```

---

## 11. Success Criteria

1. `uvicorn`, `vite`, and Claude Code can all be started locally and work together with zero config beyond `npm install` / `uv sync`.
2. All four MCP tools function end-to-end from Claude Code.
3. Demo 2 produces a visible UI change within ~2 seconds of the tool call.
4. Fuzzy resolution handles partial references ("the NVIDIA one", "live session 1") and asks for disambiguation when genuinely ambiguous.
5. `publish_recording` refuses future-dated sessions with a conversational, recoverable error message.
6. The full tutorial can be demonstrated in under 20 minutes.

---

## 12. Open Questions

| # | Question | Current lean |
|---|---|---|
| 1 | Include the "completed" checkbox in the UI to enrich `whats_next()` demos? | Yes — one field, low cost |
| 2 | Seed data: how many weeks? | 2 weeks, ~8–10 items total |
| 3 | Show streamable-HTTP transport as a stretch segment? | Mention only; keep stdio for the build |
| 4 | Also connect Claude Desktop to make the "any client" point? | Optional closing beat if time allows |
