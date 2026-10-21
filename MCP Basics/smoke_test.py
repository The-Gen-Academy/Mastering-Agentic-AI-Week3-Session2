"""Exercise modern MCP over stdio without an API key or an LLM call."""

import asyncio
import datetime
from pathlib import Path
import sys

from langchain.mcp import MCPAdapter
from mcp import Client, StdioServerParameters


SERVER = Path(__file__).resolve().with_name("mcp_server.py")
PROTOCOL = "2026-07-28"


async def main():
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    async with Client(params) as client:
        assert client.protocol_version == PROTOCOL, client.protocol_version
        print(f"SDK client protocol: {client.protocol_version}")
        tools = await client.list_tools()
        assert {tool.name for tool in tools.tools} == {
            "get_return_policy", "get_current_date", "get_product_details"
        }
        for name, arguments, expected in [
            ("get_return_policy", {}, "30 days"),
            ("get_current_date", {}, datetime.date.today().isoformat()),
            ("get_product_details", {"order_id": "1001"}, "Laptop"),
            ("get_product_details", {"order_id": "1002"}, "Tablet"),
            ("get_product_details", {"order_id": "unknown"}, "No order found"),
        ]:
            result = await client.call_tool(name, arguments)
            assert not result.is_error, result
            assert expected in " ".join(block.text for block in result.content)

        resources = await client.list_resources()
        assert {r.uri for r in resources.resources} == {"config://support-hours"}
        templates = await client.list_resource_templates()
        assert {t.uri_template for t in templates.resource_templates} == {"docs://faq/{topic}"}
        for uri, expected in [
            ("config://support-hours", "Monday-Friday"),
            ("docs://faq/returns", "30 days"),
        ]:
            resource = await client.read_resource(uri)
            assert expected in " ".join(item.text for item in resource.contents)

        prompts = await client.list_prompts()
        assert {p.name for p in prompts.prompts} == {"support_reply", "summarize_order"}
        for name, arguments, expected in [
            ("support_reply", {"customer_message": "Can I return this?"}, "Can I return this?"),
            ("summarize_order", {"order_id": "1001"}, "1001"),
        ]:
            prompt = await client.get_prompt(name, arguments)
            assert expected in " ".join(message.content.text for message in prompt.messages)

    # A known modern version can make its first request without initialize
    # or even server/discover. Each request carries the required metadata.
    async with Client(params, mode=PROTOCOL) as client:
        result = await client.call_tool("get_product_details", {"order_id": "1002"})
        assert not result.is_error
        assert "Tablet" in " ".join(block.text for block in result.content)
        print("Direct call without an initialization handshake: passed")

    # Exercise the same adapter and subprocess setup as the agent.
    async with MCPAdapter(SERVER) as adapter:
        assert adapter.client.protocol_version == PROTOCOL, adapter.client.protocol_version
        tools = await adapter.list_tools()
        tool = next(t for t in tools if t.name == "get_return_policy")
        result = await tool.ainvoke({})
        assert "30 days" in str(result), result
        print(f"LangChain adapter protocol: {adapter.client.protocol_version}")

    print("Passed: tools, resources, prompts, handshake-free call, and LangChain adapter")


if __name__ == "__main__":
    asyncio.run(main())
