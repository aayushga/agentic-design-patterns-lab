"""Actual MCP SDK protocol tests, using memory streams and one stdio subprocess."""
import asyncio
import importlib
import sys
from types import SimpleNamespace as NS

import pytest

if sys.version_info < (3, 11):
    pytest.skip("MCP SDK v2 requires Python 3.11+; legacy patterns still run on 3.10", allow_module_level=True)

from mcp import Client

app = importlib.import_module("patterns.10-model-context-protocol.app")
server_module = importlib.import_module("patterns.10-model-context-protocol.server")


def test_real_protocol_discovery_resource_prompt_and_tool():
    async def run():
        async with Client(server_module.create_server()) as client:
            result = await app.run_demo(client)
            assert result["server"] == "Support Lab" and result["protocol_version"]
            assert sorted(result["tools"]) == ["get_ticket", "list_tickets"]
            assert result["resources"] == ["support://policy"]
            assert result["prompts"] == ["triage_request"]
            assert "simulated" in result["context"]["policy"]
            assert "T-101" in result["context"]["prompt"]
            assert result["tool_result"]["status"] == "success"
            assert result["tool_result"]["output"]["ticket"]["category"] == "billing"
    asyncio.run(run())


def test_real_stdio_transport_and_client_cleanup():
    async def run():
        async with app.connect_local() as client:
            result = await app.call_tool(client, "get_ticket", {"ticket_id": "T-101"})
            assert result.status == "success" and client.server_info.name == "Support Lab"
        with pytest.raises(RuntimeError):
            await client.list_tools()
    asyncio.run(run())


def test_stdio_cleanup_preserves_caller_error():
    async def run():
        with pytest.raises(ValueError, match="caller failure"):
            async with app.connect_local():
                raise ValueError("caller failure")
    asyncio.run(run())


@pytest.mark.parametrize("name,arguments", [("get_ticket", {"ticket_id": "T-999"}),
    ("get_ticket", {"ticket_id": "bad"}), ("get_ticket", {"ticket_id": 101}),
    ("get_ticket", {}), ("list_tickets", {"priority": "urgent"}), ("unknown", {})])
def test_real_mcp_errors_are_results_not_successes(name, arguments):
    async def run():
        async with Client(server_module.create_server()) as client:
            raw = await client.call_tool(name, arguments)
            assert raw.is_error is True and raw.structured_content is None
            assert raw.content and raw.content[0].text
    asyncio.run(run())


def test_priority_filter_and_copy_of_server_data():
    async def run():
        async with Client(server_module.create_server()) as client:
            high = await app.call_tool(client, "list_tickets", {"priority": "high"})
            assert [ticket["ticket_id"] for ticket in high.output["tickets"]] == ["T-101", "T-102"]
            assert high.output["source"] == "simulated demo data"
            first = await app.call_tool(client, "get_ticket", {"ticket_id": "T-101"})
            first.output["ticket"]["summary"] = "tampered"
            second = await app.call_tool(client, "get_ticket", {"ticket_id": "T-101"})
            assert second.output["ticket"]["summary"] != "tampered"
            normal = await app.call_tool(client, "list_tickets", {"priority": "normal"})
            assert [ticket["ticket_id"] for ticket in normal.output["tickets"]] == ["T-103"]
    asyncio.run(run())


def test_host_checks_mcp_error_flag():
    async def run():
        async with Client(server_module.create_server()) as client:
            result = await app.call_tool(client, "get_ticket", {"ticket_id": "T-999"})
            assert result.status == "error" and result.output is None and "not found" in result.error
    asyncio.run(run())


def test_unallowed_host_tool_is_never_dispatched():
    class Forbidden:
        async def call_tool(self, *args):
            pytest.fail("Host must reject arbitrary tools before dispatch")
    result = asyncio.run(app.call_tool(Forbidden(), "shell", {}))
    assert result.status == "error" and "not allowed" in result.error


def test_nonobject_arguments_are_not_dispatched():
    result = asyncio.run(app.call_tool(None, "get_ticket", []))
    assert result.status == "error" and "object" in result.error


def test_missing_structured_success_data_is_not_fabricated():
    class ClientFake:
        async def call_tool(self, *args):
            return NS(is_error=False, structured_content=None)
    with pytest.raises(ValueError, match="structured"):
        asyncio.run(app.call_tool(ClientFake(), "get_ticket", {"ticket_id": "T-101"}))


def test_discovery_pagination_is_followed():
    class Pages:
        async def list_tools(self, cursor=None):
            return NS(tools=[NS(name="get_ticket" if cursor is None else "list_tickets")],
                      next_cursor="next" if cursor is None else None)
        async def list_resources(self, cursor=None):
            return NS(resources=[], next_cursor=None)
        async def list_prompts(self, cursor=None):
            return NS(prompts=[], next_cursor=None)
    assert len(asyncio.run(app.discover(Pages()))["tools"]) == 2


def test_repeated_cursor_is_rejected():
    class Pages:
        async def list_tools(self, cursor=None):
            return NS(tools=[], next_cursor="same")
    with pytest.raises(RuntimeError, match="repeated"):
        asyncio.run(app.discover(Pages()))


def test_discovery_has_a_page_limit():
    class Pages:
        calls = 0
        async def list_tools(self, cursor=None):
            self.calls += 1
            return NS(tools=[], next_cursor=str(self.calls))
    pages = Pages()
    with pytest.raises(RuntimeError, match="ten pages"):
        asyncio.run(app.discover(pages))
    assert pages.calls == 10


def test_duplicate_discovered_names_are_rejected():
    class Pages:
        async def list_tools(self, cursor=None):
            return NS(tools=[NS(name="same"), NS(name="same")], next_cursor=None)
        async def list_resources(self, cursor=None):
            return NS(resources=[], next_cursor=None)
        async def list_prompts(self, cursor=None):
            return NS(prompts=[], next_cursor=None)
    with pytest.raises(ValueError, match="duplicate"):
        asyncio.run(app.discover(Pages()))
