# MCP Course Platform Demo

A miniature course platform (a "mini Maven") used to demonstrate the value of
**MCP (Model Context Protocol)**: same backend, two consumers — the React UI
speaks raw CRUD, Claude Code speaks **intent** through a 4-tool MCP server.

See [PRD.md](PRD.md) for the full design.

```
React (Vite, :5173) ──GET──▶ FastAPI (:8000) ◀──HTTP── MCP Server (FastMCP)
                                 │                          ▲ stdio
                          data/curriculum.json         Claude Code
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python)
- Node 18+ / npm

## Run it

**1. Backend** (terminal 1):

```sh
uv sync
cd backend
uv run uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

**2. Frontend** (terminal 2):

```sh
cd frontend
npm install
npm run dev
```

Viewer: http://localhost:5173 (read-only; polls the API every 2s)

**3. Claude Code** (terminal 3, from the repo root):

```sh
claude
```

The MCP server is registered via [.mcp.json](.mcp.json) — Claude Code launches
it automatically over stdio. Run `/mcp` inside Claude Code to confirm the
`course-platform` server is connected. (The backend must be running first.)

## Other MCP clients

The same server works with any MCP client — only the registration differs.
The key gotcha: GUI/CLI clients may spawn the server from an arbitrary working
directory (Claude Desktop uses `/`), where `uv run` can't find this project's
`pyproject.toml` and the `mcp` import fails with "Server disconnected".
Pointing uv at the project explicitly (via `--directory` or `UV_PROJECT`)
fixes that.

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
      "command": "uv",
      "args": ["run", "python", "<absolute-path-to-this-repo>/mcp_server/mcp_server.py"],
      "env": {
        "UV_PROJECT": "<absolute-path-to-this-repo>"
      }
    }
  }
}
```

Notes:

- `UV_PROJECT` makes uv find the project's `pyproject.toml`/`.venv`
  regardless of where Claude Desktop spawns the process (it launches servers
  from `/`). Equivalent alternative: drop the `env` block and pass
  `"args": ["run", "--directory", "<absolute-path-to-this-repo>", "python", "mcp_server/mcp_server.py"]`.
- If the server fails with a "command not found"-style error, replace `uv`
  with its full path (`which uv`) — macOS GUI apps don't always inherit your
  shell's PATH.
- Fully quit Claude Desktop (Cmd+Q) and relaunch — the config is only read
  on startup.

### Codex CLI

Codex uses TOML at `~/.codex/config.toml`:

```toml
[mcp_servers.course-platform]
command = "uv"
args = ["run", "python", "<absolute-path-to-this-repo>/mcp_server/mcp_server.py"]

[mcp_servers.course-platform.env]
UV_PROJECT = "<absolute-path-to-this-repo>"
```

Or let Codex write the entry for you:

```sh
codex mcp add course-platform -- uv run python "<absolute-path-to-this-repo>/mcp_server/mcp_server.py"
```

Notes:

- Codex is a terminal app, so it inherits your shell's PATH — bare `uv` is
  fine.
- `UV_PROJECT` matters when you launch `codex` from outside this repo;
  explicit entries in the server's `env` table are always passed through.

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
├── .mcp.json               # Claude Code MCP registration (stdio)
├── data/curriculum.json    # mock database — single source of truth
├── backend/                # FastAPI CRUD API (no auth, file-backed)
├── mcp_server/             # FastMCP intent layer (4 tools)
└── frontend/               # React read-only viewer (polls every 2s)
```
