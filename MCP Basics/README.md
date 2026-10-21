# MCP Basics

A minimal example of the [Model Context Protocol (MCP)](https://modelcontextprotocol.io): a
[MCPServer](https://github.com/modelcontextprotocol/python-sdk) server that exposes a few support
tools, and a [LangChain](https://python.langchain.com) agent client (powered by OpenAI) that
connects to the server and answers user queries.

Updated on October 19, 2026 to MCP Python SDK **2.3.0** (the latest stable release
at upgrade time), LangChain **1.4.6**, and protocol **2026-07-28**. The server uses
the official SDK; LangChain's client adapter uses the separate FastMCP package internally.

## What's inside

| File | Description |
| --- | --- |
| [mcp_server.py](mcp_server.py) | An MCPServer exposing three tools, a static resource, a resource template, and two prompts. Runs over stdio. |
| [mcp_client.py](mcp_client.py) | A LangChain ReAct agent that launches the server, loads its tools, and answers a sample query. |
| [pyproject.toml](pyproject.toml) | Project metadata and dependencies. |
| [smoke_test.py](smoke_test.py) | Checks modern protocol selection, all three MCP primitives, a handshake-free call, and the LangChain adapter without an LLM. |

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

2. **Configure your API key.** Create or edit `.env` in this directory:
   ```bash
   OPENAI_API_KEY=your-openai-api-key-here
   ```
   The client loads this automatically via `python-dotenv`.

## Running

The client launches the MCP server for you as a subprocess through `MCPAdapter`, so
you only need to run the client:

```bash
uv run python mcp_client.py
```

To verify the MCP integration without an API key or model request:

```bash
uv run python smoke_test.py
```

This verifies that both clients select `2026-07-28`, and that a fresh client can
call a tool directly using that version without `initialize` or `server/discover`.
The latter is a test with a known server version; normal clients use automatic discovery.

`langchain.mcp` is currently a beta API and emits a beta warning. The updated
`uv.lock` records the versions tested here; it no longer holds MCP on v1.
To resolve newer compatible releases later, run `uv sync --upgrade` and rerun the smoke test.

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

1. Use the generated **STDIO** configuration for this server.
2. Click **Connect**.
3. Open the **Tools** tab and click **List Tools** to see `get_return_policy`,
   `get_current_date`, and `get_product_details`.
4. Select a tool, fill in any arguments (e.g. `order_id` = `1001` for `get_product_details`), and
   click **Run Tool** to see the response.
5. Explore **Resources** (`config://support-hours`, `docs://faq/returns`) and
   **Prompts** (`support_reply`, `summarize_order`) as well.

> **Note:** The Inspector requires [Node.js](https://nodejs.org) to be installed (it runs via
> `npx`). The `mcp dev` command itself comes from the `mcp[cli]` extra, which is already included in
> this project's dependencies (installed by `uv sync`). Press `Ctrl+C` in the terminal to stop it
> when you're done.

## How it works

1. `mcp_client.py` starts `mcp_server.py` as a subprocess and connects over stdio using
   `langchain.mcp.MCPAdapter`. Its client probes `server/discover` and selects the
   modern protocol supported by this server.
2. The server's tools are converted into LangChain tools via `adapter.list_tools()`.
3. A LangChain agent (OpenAI) reasons about the user's query and calls the appropriate MCP tool(s)
   to produce an answer.

The agent loads tools only. Resources and prompts are separate MCP operations;
they do not automatically enter the model's context. `smoke_test.py` demonstrates
reading resources and fetching prompts with the official SDK's `Client`.

## What stateless MCP means here

The [2026-07-28 protocol](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
removes protocol sessions and the `initialize` / `notifications/initialized`
handshake. Each request carries its protocol version and client capabilities.
`server/discover` advertises server support without establishing a session.
The SDK supplies this metadata and the required result fields.

Our tools already work independently: `get_product_details(order_id="1001")`
receives the order ID on every call. No handler relies on a previous call.
Keeping the stdio subprocess open avoids repeated process startup; it does not
create protocol-level session state. Stdio remains supported.

| Kind of state | Where it belongs |
| --- | --- |
| Conversation messages and agent decisions | LangChain/LangGraph; this demo makes a single invocation and has no persistent checkpointer. |
| Orders, carts, return requests | Application storage, addressed by explicit IDs on each call. |
| Protocol version and client capabilities | Metadata on each MCP request, handled by the SDK. |
| A local process or pooled HTTP connection | Transport lifecycle; it can outlive individual requests. |

For example, a future return workflow could use `start_return(order_id)` to return
a `return_id`, then `confirm_return(return_id)`. Store that workflow durably and
check authorization on each request. Do not depend on a connection-local
`current_order` variable. A Python global can still retain data in one process,
but another worker or a restart will not have it.

With Streamable HTTP, independent requests can be routed to different workers
without MCP session affinity. Shared business state still requires shared storage.
The current local stdio demo does not itself gain distributed scaling.

Other changes matter when extending the demo:

- A server needing more input returns an `input_required` result; the client sends
  the answers in a subsequent request. This replaces server-initiated requests.
- Change notifications use explicit subscriptions. Request progress can still
  stream, so stateless does not mean streaming has disappeared.
- Retrying a write operation needs application-level deduplication, such as an
  idempotency key, to avoid issuing a refund twice. Statelessness alone provides
  no exactly-once guarantee.
- Tools, resources, and prompts remain available. Their use here does not require
  adding Tasks, elicitation, subscriptions, OAuth, or an HTTP endpoint.

The [SDK can also serve older clients](https://py.sdk.modelcontextprotocol.io/protocol-versions/),
so an upgraded package alone does not prove a connection uses the modern protocol.
The smoke test checks the selected version explicitly.
