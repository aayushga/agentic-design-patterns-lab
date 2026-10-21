"""Free local A2A example; no model or remote service."""
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import SKILL, local_session, task_output


async def main():
    async with local_session() as coordinator:
        print("Agent:", coordinator.card.name)
        print("Skills:", ", ".join(s.id for s in coordinator.card.skills))
        task = await coordinator.send({"skill": SKILL, "category": "billing", "issue": "An invoice appears twice."})
        print(json.dumps(task_output(task), indent=2))
        stored = await coordinator.get(task.id)
        print("Retrieved task:", stored.id, task_output(stored)["state"])


if __name__ == "__main__":
    asyncio.run(main())
