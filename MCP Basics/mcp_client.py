from pathlib import Path

from langchain.mcp import MCPAdapter
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import asyncio


def print_step(title: str) -> None:
    print(f"\n=== {title} ===")


async def main():
    project_dir = Path(__file__).resolve().parent
    load_dotenv(project_dir / ".env")
    llm = ChatOpenAI(model="gpt-4o")

    print_step("1. Connecting to the MCP server")
    print("Launching mcp_server.py as a subprocess and talking to it over stdio...")

    # Keep the local subprocess open while the agent uses it. This is a
    # transport lifetime, not a protocol session or conversation memory.
    async with MCPAdapter(project_dir / "mcp_server.py") as adapter:
        tools = await adapter.list_tools()
        print_step(f"2. Discovered {len(tools)} tools on the server")
        for tool in tools:
            args = ", ".join(tool.args) or "no arguments"
            print(f"- {tool.name}({args}): {tool.description}")

        agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt="You are a helpful support agent."
            " You are given a user's query and you need to reason about the user's query"
            " and call the necessary tools to answer the user's query.",
        )

        user_message = "What is the return policy?"
        print_step("3. Sending the question to the agent")
        print(f"User: {user_message}")
        response = await agent.ainvoke(
            {"messages": [{"role": "user", "content": user_message}]}
        )

        # Replay the conversation to show which tools the model chose and
        # what the MCP server sent back for each call.
        print_step("4. Tool calls made by the agent")
        tool_calls_made = False
        for message in response["messages"]:
            if isinstance(message, AIMessage):
                for call in message.tool_calls:
                    tool_calls_made = True
                    print(f"Agent  -> calls '{call['name']}' with arguments {call['args']}")
            elif isinstance(message, ToolMessage):
                outcome = "returned an error" if message.status == "error" else "returned"
                print(f"Server -> '{message.name}' {outcome}: {message.text}")
        if not tool_calls_made:
            print("The agent answered without calling any tools.")

        print_step("5. Final answer")
        print(response["messages"][-1].text)


if __name__ == "__main__":
    asyncio.run(main())
