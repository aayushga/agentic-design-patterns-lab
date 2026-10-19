"""Real A2A JSON-RPC discovery and delegation, entirely inside one process."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
from typing import Awaitable, Callable
from uuid import uuid4

import httpx
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Value
from starlette.applications import Starlette
from a2a.client import A2ACardResolver
from a2a.client.transports.jsonrpc import JsonRpcTransport
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (
    AgentCapabilities, AgentCard, AgentInterface, AgentSkill, GetTaskRequest,
    Message, Part, Role, SendMessageRequest, Task, TaskState, TaskStatus,
)
from a2a.utils.errors import TaskNotCancelableError

BASE_URL = "http://support.local"
RPC_URL = BASE_URL + "/a2a/jsonrpc"
SKILL = "triage_support"
CATEGORIES = ("billing", "support", "sales")
MAX_MESSAGE_CHARS = 3000
MAX_SUBMISSIONS = 3
Responder = Callable[[dict], Awaitable[dict]]


def agent_card() -> AgentCard:
    return AgentCard(
        name="DemoDesk support specialist", description="Fictional ticket triage; no account actions.",
        version="1.0.0", capabilities=AgentCapabilities(streaming=False, push_notifications=False),
        default_input_modes=["text/plain"], default_output_modes=["application/json"],
        skills=[AgentSkill(id=SKILL, name="Triage a ticket",
                           description="Request missing issue details, then return a triage report.",
                           tags=["support", "triage"], examples=['{"skill":"triage_support","category":"support","issue":"Cannot sign in"}'])],
        supported_interfaces=[AgentInterface(protocol_binding="JSONRPC", protocol_version="1.0", url=RPC_URL)],
    )


def parse_ticket(text: str) -> dict:
    if not isinstance(text, str) or not 1 <= len(text) <= MAX_MESSAGE_CHARS:
        raise ValueError("Send a JSON ticket of at most 3000 characters.")
    try:
        ticket = json.loads(text)
    except ValueError as exc:
        raise ValueError("Ticket must be valid JSON.") from exc
    if not isinstance(ticket, dict) or set(ticket) != {"skill", "category", "issue"}:
        raise ValueError("Ticket needs exactly skill, category, and issue.")
    if ticket["skill"] != SKILL:
        raise ValueError("Unsupported skill; use triage_support.")
    if ticket["category"] not in CATEGORIES:
        raise ValueError("Category must be billing, support, or sales.")
    if not isinstance(ticket["issue"], str) or len(ticket["issue"]) > 2000:
        raise ValueError("Issue must be text of at most 2000 characters.")
    return {**ticket, "issue": ticket["issue"].strip()}


def validate_report(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != {"priority", "summary", "next_step"}:
        raise ValueError("Invalid specialist report fields")
    if value["priority"] not in ("normal", "high"):
        raise ValueError("Invalid specialist priority")
    for field in ("summary", "next_step"):
        if not isinstance(value[field], str) or not 1 <= len(value[field].strip()) <= 1000:
            raise ValueError("Invalid specialist report text")
    return value


async def local_responder(ticket: dict) -> dict:
    steps = {
        "support": "Check the error message and try the documented account recovery steps.",
        "billing": "Ask billing to review the invoice; no refund has been approved.",
        "sales": "Ask sales to discuss requirements and available plans.",
    }
    return {"priority": "normal", "summary": ticket["issue"][:1000], "next_step": steps[ticket["category"]]}


class SupportExecutor(AgentExecutor):
    """The SDK owns task persistence; the responder owns only report generation."""

    def __init__(self, responder: Responder = local_responder):
        self.responder = responder
        self.submissions: dict[str, int] = {}

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task
        if task is None:
            task = Task(id=context.task_id, context_id=context.context_id,
                        status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED), history=[context.message])
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue=event_queue, task_id=task.id, context_id=task.context_id)

        def message(text: str) -> Message:
            return updater.new_agent_message(parts=[Part(text=text)])

        # Count execution attempts independently of asynchronous history updates.
        self.submissions[task.id] = self.submissions.get(task.id, 0) + 1
        if self.submissions[task.id] > MAX_SUBMISSIONS:
            await updater.reject(message("Submission limit reached; create a new task."))
            return
        try:
            ticket = parse_ticket(context.get_user_input())
        except ValueError as exc:
            await updater.reject(message(str(exc)))
            return
        if not ticket["issue"]:
            await updater.requires_input(message("Describe the issue. Resubmit the complete ticket with the same task and context IDs."))
            return
        await updater.start_work(message("Preparing a fictional triage report."))
        try:
            # Cooperative deadline, one responder attempt, no automatic retries.
            report = validate_report(await asyncio.wait_for(self.responder(ticket), timeout=35))
        except Exception:
            await updater.failed(message("Specialist could not produce a valid report. No account action was taken."))
            return
        await updater.add_artifact(
            parts=[Part(data=ParseDict(report, Value()), media_type="application/json")],
            name="triage-report", last_chunk=True,
        )
        await updater.complete(message("Triage report prepared. The underlying issue is not marked resolved."))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise TaskNotCancelableError(message="This short request/response demo does not support cancellation.")


class Coordinator:
    def __init__(self, transport: JsonRpcTransport, card: AgentCard):
        self.transport, self.card = transport, card

    async def send(self, ticket: dict, *, task_id: str = "", context_id: str = "") -> Task:
        if bool(task_id) != bool(context_id):
            raise ValueError("Supply both task_id and context_id when resuming.")
        text = json.dumps(ticket, ensure_ascii=False)
        if len(text) > MAX_MESSAGE_CHARS:
            raise ValueError("Ticket exceeds the message size limit.")
        response = await self.transport.send_message(SendMessageRequest(message=Message(
            role=Role.ROLE_USER, message_id=uuid4().hex, task_id=task_id, context_id=context_id,
            parts=[Part(text=text)],
        )))
        if not response.HasField("task"):
            raise RuntimeError("Specialist returned no task")
        return response.task

    async def get(self, task_id: str) -> Task:
        return await self.transport.get_task(GetTaskRequest(id=task_id))


@asynccontextmanager
async def local_session(responder: Responder = local_responder):
    """A real HTTP/JSON-RPC exchange via ASGITransport, without opening a socket."""
    card = agent_card()
    handler = DefaultRequestHandler(agent_executor=SupportExecutor(responder),
                                    task_store=InMemoryTaskStore(), agent_card=card)
    app = Starlette(routes=[*create_agent_card_routes(card),
                            *create_jsonrpc_routes(handler, rpc_url="/a2a/jsonrpc")])
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE_URL, headers={"A2A-Version": "1.0"}, timeout=40) as http:
            discovered = await A2ACardResolver(http, BASE_URL).get_agent_card()
            if not any(s.id == SKILL for s in discovered.skills):
                raise ValueError("Specialist does not advertise the expected skill")
            # Fixed local interface, never an arbitrary URL selected by a model/card.
            if not any(i.url == RPC_URL and i.protocol_binding == "JSONRPC" for i in discovered.supported_interfaces):
                raise ValueError("Unexpected specialist interface")
            transport = JsonRpcTransport(http, discovered, RPC_URL)
            try:
                yield Coordinator(transport, discovered)
            finally:
                await transport.close()
    finally:
        await handler.aclose()


def task_output(task: Task) -> dict:
    result = {"task_id": task.id, "context_id": task.context_id,
              "state": TaskState.Name(task.status.state).removeprefix("TASK_STATE_").lower(),
              "message": " ".join(p.text for p in task.status.message.parts if p.HasField("text")),
              "artifacts": []}
    for artifact in task.artifacts:
        result["artifacts"].append({"name": artifact.name, "data": [MessageToDict(p.data) for p in artifact.parts if p.HasField("data")]})
    return result


async def demo() -> None:
    async with local_session() as coordinator:
        print("Discovered:", coordinator.card.name)
        task = await coordinator.send({"skill": SKILL, "category": "support", "issue": "Cannot sign in after resetting my password."})
        print(json.dumps(task_output(task), indent=2))


if __name__ == "__main__":
    asyncio.run(demo())
