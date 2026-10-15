"""Local MCP host: negotiate, discover, read context, and call a real stdio server."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
import json
import sys

ALLOWED_TOOLS = {"get_ticket", "list_tickets"}
POLICY_URI = "support://policy"


@asynccontextmanager
async def connect_local():
    """Launch only this repository's server using this interpreter; close on exit."""
    if sys.version_info < (3, 11):
        raise RuntimeError("Pattern 10 requires Python 3.11+ and the official MCP SDK v2")
    from mcp import Client, StdioServerParameters
    parameters = StdioServerParameters(command=sys.executable,
        args=["-B", str(Path(__file__).resolve().with_name("server.py"))])
    error = None
    async with Client(parameters, read_timeout_seconds=10.0) as client:
        try:
            yield client
        except Exception as exc:
            # Close SDK task groups normally before propagating the caller error.
            error = exc
    if error is not None:
        raise error


async def _collect(client, method: str, attribute: str) -> list:
    """Handle MCP discovery pagination with a bound and cursor-loop detection."""
    items, seen = [], set()
    cursor = None
    for _ in range(10):
        page = await getattr(client, method)(cursor=cursor)
        items.extend(getattr(page, attribute))
        cursor = page.next_cursor
        if cursor is None:
            return items
        if cursor in seen:
            raise RuntimeError("MCP discovery repeated a pagination cursor")
        seen.add(cursor)
    raise RuntimeError("MCP discovery exceeded ten pages")


async def discover(client) -> dict:
    tools = await _collect(client, "list_tools", "tools")
    resources = await _collect(client, "list_resources", "resources")
    prompts = await _collect(client, "list_prompts", "prompts")
    names = [tool.name for tool in tools]
    if len(set(names)) != len(names):
        raise ValueError("MCP server advertised duplicate tool names")
    return {"tools": tools, "resources": resources, "prompts": prompts}


async def load_context(client, query: str) -> dict[str, str]:
    """The host selects a resource and a prompt; neither invokes an LLM."""
    resource = await client.read_resource(POLICY_URI)
    if not resource.contents or not all(isinstance(getattr(block, "text", None), str) for block in resource.contents):
        raise ValueError("Expected a text policy resource")
    prompt = await client.get_prompt("triage_request", arguments={"request": query})
    if not prompt.messages or not all(isinstance(getattr(message.content, "text", None), str)
                                      for message in prompt.messages):
        raise ValueError("Expected a text triage prompt")
    return {"policy": "\n".join(block.text for block in resource.contents),
            "prompt": "\n".join(message.content.text for message in prompt.messages)}


@dataclass
class ToolObservation:
    name: str
    arguments: dict
    status: str
    output: dict | None = None
    error: str | None = None


async def call_tool(client, name: str, arguments: dict) -> ToolObservation:
    """Never report an MCP is_error result as a successful tool response."""
    if not isinstance(name, str) or name not in ALLOWED_TOOLS:
        return ToolObservation(str(name), arguments, "error", error="Tool is not allowed by this host")
    if not isinstance(arguments, dict):
        return ToolObservation(name, {}, "error", error="Tool arguments must be an object")
    result = await client.call_tool(name, arguments)
    if result.is_error:
        text = "\n".join(block.text for block in result.content if isinstance(getattr(block, "text", None), str))
        return ToolObservation(name, arguments, "error", error=text or "MCP tool failed")
    if not isinstance(result.structured_content, dict):
        raise ValueError("Expected structured data from the demo tool")
    return ToolObservation(name, arguments, "success", output=result.structured_content)


async def run_demo(client) -> dict:
    catalog = await discover(client)
    context = await load_context(client, "What is reported in T-101?")
    result = await call_tool(client, "get_ticket", {"ticket_id": "T-101"})
    return {"server": client.server_info.name if client.server_info else "unreported",
            "protocol_version": client.protocol_version,
            "tools": [tool.name for tool in catalog["tools"]],
            "resources": [str(resource.uri) for resource in catalog["resources"]],
            "prompts": [prompt.name for prompt in catalog["prompts"]],
            "context": context, "tool_result": asdict(result)}


async def _main():
    async with connect_local() as client:
        print(json.dumps(await run_demo(client), indent=2))


def main():
    asyncio.run(_main())


if __name__ == "__main__":
    main()
