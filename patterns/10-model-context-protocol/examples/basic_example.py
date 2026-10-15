"""Discover a real local MCP server and read a fictional ticket through it."""
import asyncio
from pathlib import Path
import sys

if __package__:
    from ..app import connect_local, discover, call_tool
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import connect_local, discover, call_tool


async def main():
    async with connect_local() as client:
        catalog = await discover(client)
        print("Connected to:", client.server_info.name)
        print("Discovered tools:", sorted(tool.name for tool in catalog["tools"]))
        result = await call_tool(client, "get_ticket", {"ticket_id": "T-101"})
        print("MCP tool status:", result.status)
        print("Tool result:", result.output)


if __name__ == "__main__":
    asyncio.run(main())
