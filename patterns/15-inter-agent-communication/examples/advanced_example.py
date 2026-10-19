"""Free local A2A example; no model or remote service."""
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import SKILL, local_session, task_output


async def main():
    async with local_session() as coordinator:
        ticket = {"skill": SKILL, "category": "support", "issue": ""}
        pending = await coordinator.send(ticket)
        print("1. Missing details:", json.dumps(task_output(pending), indent=2))
        ticket["issue"] = "Password reset link has expired."
        done = await coordinator.send(ticket, task_id=pending.id, context_id=pending.context_id)
        print("2. Resumed same task:", done.id == pending.id and done.context_id == pending.context_id)
        print(json.dumps(task_output(done), indent=2))
        rejected = await coordinator.send({**ticket, "skill": "issue_refund"})
        print("3. Unsupported skill:", task_output(rejected)["state"], task_output(rejected)["message"])

    async def unavailable(ticket):
        raise RuntimeError("Simulated private backend failure")

    async with local_session(unavailable) as coordinator:
        failed = await coordinator.send(ticket)
        print("4. Specialist failure:", json.dumps(task_output(failed), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
