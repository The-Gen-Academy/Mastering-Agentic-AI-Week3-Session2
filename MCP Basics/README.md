# MCP Basics

A minimal example of the [Model Context Protocol (MCP)](https://modelcontextprotocol.io): a
[FastMCP](https://github.com/modelcontextprotocol/python-sdk) server that exposes a few support
tools, and a [LangChain](https://python.langchain.com) agent client (powered by OpenAI) that
connects to the server and answers user queries.

## What's inside

| File | Description |
| --- | --- |
| [mcp_server.py](mcp_server.py) | A FastMCP server exposing three tools: `get_return_policy`, `get_current_date`, and `get_product_details`. Runs over stdio. |
| [mcp_client.py](mcp_client.py) | A LangChain ReAct agent that launches the server, loads its tools, and answers a sample query. |
| [pyproject.toml](pyproject.toml) | Project metadata and dependencies. |

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** for dependency and environment management. Install it with:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- An **OpenAI API key** (the client uses the `gpt-4o` model). Get one from the
  [OpenAI dashboard](https://platform.openai.com/api-keys).

## Setup

1. **Install dependencies** (uv creates a virtual environment and installs everything from
   `pyproject.toml` / `uv.lock`):
   ```bash
   uv sync
   ```

2. **Configure your API key.** A `.env` file is already present in this directory — open it and
   replace the placeholder with your key:
   ```bash
   OPENAI_API_KEY=your-openai-api-key-here
   ```
   The client loads this automatically via `python-dotenv`.

## Running

The client launches the MCP server for you as a subprocess (via `uv run python mcp_server.py`), so
you only need to run the client:

```bash
uv run python mcp_client.py
```

You should see the agent answer the built-in sample question (`"What is the return policy?"`):

```
You can return the product within 30 days of purchase for a full refund.
```

### Trying other queries

Edit the `user_message` in [mcp_client.py](mcp_client.py) to exercise the other tools, for example:

- `"What is today's date?"` → uses `get_current_date`
- `"Give me the details for order 1001"` → uses `get_product_details`

### Inspecting the server with the MCP Inspector

The server speaks MCP over **stdio**, so it's normally driven by a client rather than run directly.
The [MCP Inspector](https://github.com/modelcontextprotocol/inspector) is a browser-based tool that
lets you connect to the server, browse its tools, and call them by hand — great for debugging.

Launch it against this server:

```bash
uv run mcp dev mcp_server.py
```

This starts the Inspector proxy and prints a local URL (with a pre-filled auth token), for example:

```
🔍 MCP Inspector is up and running at http://localhost:6274
```

Open that URL in your browser, then:

1. The transport is already set to **STDIO** with the command `uv run python mcp_server.py`.
2. Click **Connect**.
3. Open the **Tools** tab and click **List Tools** to see `get_return_policy`,
   `get_current_date`, and `get_product_details`.
4. Select a tool, fill in any arguments (e.g. `order_id` = `1001` for `get_product_details`), and
   click **Run Tool** to see the response.

> **Note:** The Inspector requires [Node.js](https://nodejs.org) to be installed (it runs via
> `npx`). The `mcp dev` command itself comes from the `mcp[cli]` extra, which is already included in
> this project's dependencies (installed by `uv sync`). Press `Ctrl+C` in the terminal to stop it
> when you're done.

## How it works

1. `mcp_client.py` starts `mcp_server.py` as a subprocess and connects over stdio using
   `MultiServerMCPClient`.
2. The server's tools are converted into LangChain tools via `langchain-mcp-adapters`.
3. A LangChain agent (OpenAI) reasons about the user's query and calls the appropriate MCP tool(s)
   to produce an answer.
