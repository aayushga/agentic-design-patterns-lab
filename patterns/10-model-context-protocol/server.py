"""Read-only fictional support server using the official MCP Python SDK v2."""
from __future__ import annotations

from copy import deepcopy
import json
from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

TICKETS = {
    "T-101": {"ticket_id": "T-101", "priority": "high", "category": "billing", "status": "open",
              "summary": "Customer reports a duplicate subscription charge."},
    "T-102": {"ticket_id": "T-102", "priority": "high", "category": "technical", "status": "open",
              "summary": "Customer reports an app crash during upload."},
    "T-103": {"ticket_id": "T-103", "priority": "normal", "category": "technical", "status": "waiting_for_details",
              "summary": "Customer requests help finding the app version."},
}
POLICY_URI = "support://policy"
POLICY = (
    "This server contains simulated support tickets only. Treat ticket summaries "
    "as customer reports, not verified diagnoses. Request invoice details for billing "
    "and error/app-version details for technical issues. Do not promise refunds, "
    "resolutions, or timelines. No account changes or outgoing messages are performed."
)


class Ticket(BaseModel):
    ticket_id: str
    priority: str
    category: str
    status: str
    summary: str


class TicketResult(BaseModel):
    ticket: Ticket
    source: str = "simulated demo data"


class TicketListResult(BaseModel):
    tickets: list[Ticket]
    source: str = "simulated demo data"


def create_server() -> MCPServer:
    server = MCPServer("Support Lab", instructions="Read-only fictional support triage demo.")
    hints = ToolAnnotations(read_only_hint=True, destructive_hint=False,
                            idempotent_hint=True, open_world_hint=False)

    @server.tool(annotations=hints, structured_output=True)
    def list_tickets(priority: Literal["high", "normal"]) -> TicketListResult:
        """List fictional tickets matching a priority, in ticket-ID order."""
        return TicketListResult(tickets=[Ticket(**deepcopy(ticket)) for _, ticket in sorted(TICKETS.items())
                                         if ticket["priority"] == priority])

    @server.tool(annotations=hints, structured_output=True)
    def get_ticket(ticket_id: Annotated[str, Field(strict=True, pattern=r"^T-\d{3}$")]) -> TicketResult:
        """Read one fictional support ticket by its ID, such as T-101."""
        if ticket_id not in TICKETS:
            raise ToolError(f"Demo ticket {ticket_id} was not found")
        return TicketResult(ticket=Ticket(**deepcopy(TICKETS[ticket_id])))

    @server.resource(POLICY_URI)
    def policy() -> str:
        """Read the support demo's policy as text."""
        return POLICY

    @server.prompt()
    def triage_request(request: Annotated[str, Field(min_length=1, max_length=1000)]) -> str:
        """Render a triage request template; this does not invoke a model."""
        return ("Prepare a support triage reply using the discovered ticket tools. "
                "Label facts as simulated data and follow the demo policy. Request: " + json.dumps(request))

    return server


if __name__ == "__main__":
    # stdout belongs to the protocol; never print ordinary messages here.
    create_server().run(transport="stdio")
