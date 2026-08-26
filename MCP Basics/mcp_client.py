from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import asyncio


load_dotenv()

llm = ChatOpenAI(model="gpt-4o")


async def main():
    client = MultiServerMCPClient(
        {
            "support": {
                "command": "uv",  # Run the server inside the project's uv environment
                "args": ["run", "python", "mcp_server.py"],  # Arguments to the command
                "transport": "stdio",
            }
        }
    )

    # Get tools (MultiServerMCPClient manages the session for you)
    tools = await client.get_tools()

    # Create a react-style agent
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt="You are a helpful support agent."
        " You are given a user's query and you need to reason about the user's query"
        " and call the necessary tools to answer the user's query.",
    )

    user_message = "What is the return policy?"

    # Invoke the support agent
    response = await agent.ainvoke(
        {"messages": [{"role": "user", "content": user_message}]}
    )
    print(response["messages"][-1].content)


if __name__ == "__main__":
    asyncio.run(main())
