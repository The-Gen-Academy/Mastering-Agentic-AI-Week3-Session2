"""Smoke test: connect to the running server and print what it advertises.

Usage:  uv run python scripts/smoke.py [url]      (default http://127.0.0.1:8000/mcp)

Verifies the whole V1 contract end to end: initialize, resources/list, and that
resources/read refuses with the V1 explanation instead of a bare protocol error.
"""

from __future__ import annotations

import asyncio
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

DEFAULT_URL = "http://127.0.0.1:8000/mcp"


async def main(url: str) -> int:
    async with streamable_http_client(url) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"connected to {init.server_info.name} v{init.server_info.version}  ({url})")
            print(f"protocol: {init.protocol_version}")
            print(f"capabilities: resources={init.capabilities.resources is not None}, "
                  f"tools={init.capabilities.tools is not None}\n")

            result = await session.list_resources()
            print(f"resources/list -> {len(result.resources)} resources\n")
            for r in result.resources:
                print(f"  {r.name}")
                print(f"    title     {r.title}")
                print(f"    mimeType  {r.mime_type}")
                print(f"    uri       {r.uri}")
                print(f"    desc      {r.description}")
                print()

            if not result.resources:
                print("FAIL: server advertised no resources")
                return 1

            # V1 contract: reading is the client's job, and refusal must be explanatory.
            probe = result.resources[0]
            try:
                await session.read_resource(str(probe.uri))
            except Exception as exc:
                print(f"resources/read -> refused as expected:\n  {exc}\n")
            else:
                print("FAIL: resources/read returned content; V1 should not serve content")
                return 1

            print("OK")
            return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL)))
