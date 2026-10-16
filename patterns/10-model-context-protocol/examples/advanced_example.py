"""Demonstrate resources, prompt rendering, filtered tools, and MCP errors."""
import asyncio
from pathlib import Path
import sys

if __package__:
    from ..app import connect_local, discover, load_context, call_tool
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import connect_local, discover, load_context, call_tool


async def main():
    async with connect_local() as client:
        catalog = await discover(client)
        print("Resources:", [str(item.uri) for item in catalog["resources"]])
        print("Prompts:", [item.name for item in catalog["prompts"]])
        context = await load_context(client, "Summarize high-priority tickets.")
        print("Policy resource:", context["policy"])
        print("Rendered prompt:", context["prompt"])
        filtered = await call_tool(client, "list_tickets", {"priority": "high"})
        print("High-priority tickets:", filtered.output)
        missing = await call_tool(client, "get_ticket", {"ticket_id": "T-999"})
        print("Missing ticket:", missing.status, missing.error)
        invalid = await call_tool(client, "get_ticket", {"ticket_id": "bad-id"})
        print("Invalid arguments:", invalid.status)
        print("No model request or real ticket update occurred.")


if __name__ == "__main__":
    asyncio.run(main())
