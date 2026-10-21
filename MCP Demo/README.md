# MCP Course Platform Demo

A miniature course platform (a "mini Maven") used to demonstrate the value of
**MCP (Model Context Protocol)**: same backend, two consumers — the React UI
speaks raw CRUD, Claude Code speaks **intent** through a 4-tool MCP server.

See [PRD.md](PRD.md) for the full design.

```
React (Vite, :5173) ──GET──▶ FastAPI (:8000) ◀──HTTP── MCP Server (MCPServer)
                                 │                          ▲ stdio
                          data/curriculum.json         Claude Code
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python)
- Node 18+ / npm
- macOS or Linux with Bash

## Setup

From this project's root, run:

```sh
./dev setup
```

This installs the locked Python and frontend dependencies, uses Python 3.12
from `.python-version`, and generates `.mcp.json` for the current folder.
It preserves other MCP server registrations and custom course API settings.
`uv` can download Python if the requested version is not installed.

The `dev` launcher resolves its own location and always uses this project's
`.venv`. It ignores inherited `VIRTUAL_ENV`, `UV_PROJECT`, and alternate
environment paths. It recreates the generated environment when its recorded
project location changes, repairing activation scripts and executable paths.
It starts Uvicorn with `python -m uvicorn`.

**You do not need to activate `.venv`.** An old `(mcp-course-demo)` prompt can
be cleared with `deactivate` or by opening a new terminal. The launcher works
even while that old activation is present; it cannot change its parent shell.

After moving or cloning the folder, run `./dev setup` again before reconnecting
your MCP client. External client registrations must point to the new `dev`
path. Do not copy `.venv` or `frontend/node_modules` between machines.
The `.venv.before-path-fix-*` folder is only an inactive recovery backup.

## Run it

**1. Backend** (terminal 1):

```sh
./dev backend
```

API docs: http://localhost:8000/docs

**2. Frontend** (terminal 2):

```sh
./dev frontend
```

Viewer: http://localhost:5173 (read-only; polls the API every 2s)

**3. Claude Code** (terminal 3, from the repo root):

```sh
claude
```

The MCP server is registered via [.mcp.json](.mcp.json) — Claude Code launches
it automatically over stdio. Run `/mcp` inside Claude Code to confirm the
`course-platform` server is connected. (The backend must be running first.)

`.mcp.json` is generated locally and excluded from version control because it
contains machine-specific paths. After upgrading or moving the project,
restart the MCP connection so the client launches the new server process.

Run `../dev backend` if your terminal is already inside `backend/`. From any
other working directory, use the absolute path to `dev`, quoted if it contains
spaces. The same applies to every launcher command.

Other useful commands:

```sh
./dev test
./dev build
./dev python -c 'import sys; print(sys.executable)'
```

## MCP version and migration

Verified on **20 October 2026**: the latest stable official Python SDK is
[`mcp` 2.3.0](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0).
`pyproject.toml` requires `mcp>=2.3.0,<3`, and `uv.lock` fixes the installed
version at 2.3.0. Use `./dev setup` for repeatable installs; future 2.x
upgrades should be explicit (`uv lock --upgrade-package mcp`, then
`./dev setup` and the tests below).

The [v2 migration](https://py.sdk.modelcontextprotocol.io/migration/) replaces
the SDK's `FastMCP` import with `from mcp.server import MCPServer`.
The four tool names and arguments are unchanged. The server uses explicit
stdio transport, reports its own application version, and advertises
read-only/write annotations. These annotations are client hints, not
authorization controls. Expected backend HTTP and connection failures use
`ToolError` so v2 can expose actionable messages to the calling model.
`COURSE_API_URL` optionally overrides `http://localhost:8000`.

The SDK supports the
[2026-07-28 protocol](https://py.sdk.modelcontextprotocol.io/whats-new/)
and legacy 2025-11-25 clients on the same server. Modern requests carry
protocol metadata and use discovery instead of the legacy initialization
handshake. Keeping stdio is appropriate for this locally launched demo.
The SDK handles the wire changes; this project does not need custom
protocol negotiation.

Run the migration checks:

```sh
./dev test
```

These launch a temporary backend and real stdio server subprocesses, verify
modern discovery and legacy initialization, list and call all four tools,
check recording creation/replacement and future-session refusal, and check
input validation and error handling. Writes use a temporary curriculum;
the demo's `data/curriculum.json` is not modified.
Setup regression tests also move a temporary project, supply stale shell
environment variables, and verify that its Python environment and Uvicorn
launcher are rebuilt at the new location.

## Recommended follow-up changes

- **Make dates timezone-aware.** `_session_end()` and `whats_next()` use the
  host's naive local clock even though items have a timezone. Use IANA zones
  such as `Asia/Kolkata` and aware datetimes for publication guards and
  “today” classification. The current `GMT+5:30` values need normalization.
- **Validate recording URLs in the API and MCP layer.** Currently arbitrary
  strings are stored as links. Require valid HTTP(S) URLs and return a
  useful validation error before writing.
- **Make the demo clock reproducible.** Seed dates age, so the “future
  session” demonstration eventually stops exercising its guard. Add a
  configurable demo clock or a seed-date shifting command.
- **Protect concurrent writes.** The file lock protects individual reads
  and saves, not the entire read/modify/write transaction. Use a transactional
  database or lock the whole update before supporting simultaneous writers.
- **For remote deployment, add Streamable HTTP and authorization together.**
  Keep this unauthenticated backend local. A hosted version needs user identity,
  instructor-only publication rights enforced by the backend, restricted CORS,
  and per-user completion state. Follow the
  [SDK deployment guidance](https://py.sdk.modelcontextprotocol.io/)
  when adding remote MCP access.
- **Optional richer MCP demonstrations:** return typed domain objects alongside
  readable summaries, expose curriculum resources, or demonstrate elicitation
  for ambiguous session names. Current string return types already produce
  structured results through the SDK. New elicitation flows should use v2's
  `Resolve` mechanism for compatibility across protocol versions; no such
  change is required for the current tools.

## Other MCP clients

The same server works with other stdio MCP clients. Use the same `dev mcp`
launcher so arbitrary working directories and stale shell activation cannot
select another project environment. Launcher diagnostics go to stderr;
stdout is reserved for the MCP protocol.

In the snippets below, replace:

- `<absolute-path-to-this-repo>` — where you cloned this repo
  (e.g. `/Users/you/Desktop/MCP Demo`)
- `<absolute-path-to-uv>` — output of `which uv`
  (e.g. `/opt/homebrew/bin/uv`)

### Claude Desktop

Edit the config (Settings → Developer → Edit Config), which lives at
`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS:

```json
{
  "mcpServers": {
    "course-platform": {
      "command": "/bin/bash",
      "args": ["<absolute-path-to-this-repo>/dev", "mcp"],
      "env": {
        "UV_BIN": "<absolute-path-to-uv>"
      }
    }
  }
}
```

Notes:

- You can copy the `course-platform` entry generated by `./dev setup` into
  your client configuration.
- `UV_BIN` points to uv directly because GUI apps may have a limited PATH.
- Fully quit Claude Desktop (Cmd+Q) and relaunch — the config is only read
  on startup.

### Codex CLI

Codex uses TOML at `~/.codex/config.toml`:

```toml
[mcp_servers.course-platform]
command = "/bin/bash"
args = ["<absolute-path-to-this-repo>/dev", "mcp"]

[mcp_servers.course-platform.env]
UV_BIN = "<absolute-path-to-uv>"
```

Whichever client you use, the FastAPI backend (`:8000`) must be running or
the tools will return connection errors.

## The MCP tools

| Tool | Try saying |
|---|---|
| `get_schedule(week?)` | "Show me what's happening in week 2" |
| `get_session_details(session)` | "Get me the slides link for the NVIDIA guest lecture" |
| `publish_recording(session, url)` | "The recording for Live Session 1 week 1 is up: https://…" |
| `whats_next()` | "What should I focus on?" |

## Demo script

1. Tour the viewer at :5173, then the raw API at :8000/docs.
2. **Fetch:** ask Claude for the NVIDIA lecture's slides link.
3. **Publish:** give Claude a recording URL for a *past* session — watch the
   dashed "Recording · soon" placeholder on :5173 turn into a live button
   within ~2 seconds.
4. **Guard rail:** try publishing a recording for a *future* session — the
   tool refuses conversationally.
5. **Intent showcase:** ask "what should I focus on?" — `whats_next()`
   composes an answer no single API endpoint provides.

## Reset the demo

The JSON file is the database. To restore the seed state:

```sh
cp data/curriculum.seed.json data/curriculum.json
```

## Project layout

```
├── PRD.md                  # product/design doc
├── dev                     # setup and launch commands, independent of caller cwd
├── .python-version         # Python version selected by uv
├── .mcp.json               # generated local MCP registration (stdio)
├── scripts/                # configuration generation
├── data/curriculum.json    # mock database — single source of truth
├── backend/                # FastAPI CRUD API (no auth, file-backed)
├── mcp_server/             # MCPServer intent layer (4 tools)
├── tests/                  # isolated MCP migration/integration checks
└── frontend/               # React read-only viewer (polls every 2s)
```
