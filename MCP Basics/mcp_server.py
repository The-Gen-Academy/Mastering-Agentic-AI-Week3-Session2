from mcp.server.fastmcp import FastMCP
import datetime

# Create an MCP server
mcp = FastMCP("Langgraph_MCP_Server")


# Add an addition tool
@mcp.tool()
def get_return_policy() -> str:  
    """Provide the return policy for the product"""
    return "You can return the product within 30 days of purchase for a full refund."

@mcp.tool()
def get_current_date() -> str:
    """ Provide the current date in yyyy-mm-dd format """
    current_time = datetime.datetime.now()
    return current_time.strftime("%Y-%m-%d")

@mcp.tool()
def get_product_details(order_id: str) -> str:
    """Provide the product details for the given order ID"""
    order_details = {
        '1001': {'product_name': 'Laptop', 'date_of_purchase': '2025-05-01', 'quantity': 1, 'price': 100},
        '1002': {'product_name': 'Tablet', 'date_of_purchase': '2025-04-01', 'quantity': 1, 'price': 100},
    }
    if order_id not in order_details:
        return f"No order found with ID {order_id}. Please check the order ID and try again."
    return f"The product details for order {order_id} are as follows:\
          product_name: {order_details[order_id]['product_name']},\
          date_of_purchase: {order_details[order_id]['date_of_purchase']}, \
          quantity: {order_details[order_id]['quantity']}, \
          price: {order_details[order_id]['price']}"

# --- Resources ---
# Resources expose read-only data the client can fetch by URI.

@mcp.resource("config://support-hours")
def support_hours() -> str:
    """Static resource: customer support availability."""
    return "Customer support is available Monday-Friday, 9am-6pm EST."

@mcp.resource("docs://faq/{topic}")
def faq(topic: str) -> str:
    """Templated resource: reference FAQ content by topic (e.g. returns, shipping)."""
    articles = {
        'returns': "Items can be returned within 30 days of purchase for a full refund.",
        'shipping': "Standard shipping takes 3-5 business days. Free on orders over $50.",
        'warranty': "All electronics include a 1-year limited manufacturer warranty.",
    }
    return articles.get(topic, f"No FAQ article found for topic '{topic}'.")


# --- Prompts ---
# Prompts are reusable message templates the client can surface to the user.

@mcp.prompt()
def support_reply(customer_message: str) -> str:
    """Draft a polite customer-support reply to the given message."""
    return (
        "You are a friendly customer support agent. "
        "Write a polite, helpful reply to the following customer message:\n\n"
        f"{customer_message}"
    )

@mcp.prompt()
def summarize_order(order_id: str) -> str:
    """Ask the model to summarize an order in plain language."""
    return f"Look up order {order_id} and summarize its details for the customer in one short paragraph."


if __name__ == "__main__":
    mcp.run() #stdio