"""Memory Management: bounded chat history, session state, and explicit SQLite preferences.

Only remember commands persist preferences. Chat turns and support issues stay
in memory for the current Session. This is a single-threaded educational demo.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re
import sqlite3
from tempfile import TemporaryDirectory
from typing import Callable

PREFERENCE_VALUES = {
    "reply_style": {"concise", "detailed"},
    "preferred_language": {"english", "spanish"},
}


def _identifier(value: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 64:
        raise ValueError("User/session IDs must contain text and be at most 64 characters")


@dataclass
class Turn:
    query: str
    response: str


@dataclass
class Session:
    user_id: str
    session_id: str
    max_turns: int = 3
    history: list[Turn] = field(default_factory=list, init=False)
    state: dict[str, str] = field(default_factory=dict, init=False)
    profile_version: int | None = field(default=None, init=False)
    _identity: tuple[str, str] = field(init=False, repr=False)

    def __post_init__(self):
        _identifier(self.user_id)
        _identifier(self.session_id)
        if type(self.max_turns) is not int or not 1 <= self.max_turns <= 10:
            raise ValueError("max_turns must be an integer between 1 and 10")
        self._identity = (self.user_id, self.session_id)


class MemoryStore:
    """Caller-supplied user IDs namespace profiles; they are not authentication."""
    def __init__(self, db_path: str | Path):
        self.connection = sqlite3.connect(str(db_path))
        try:
            with self.connection:
                self.connection.execute(
                    "CREATE TABLE IF NOT EXISTS profiles ("
                    "user_id TEXT PRIMARY KEY, version INTEGER NOT NULL, facts TEXT NOT NULL)"
                )
        except Exception:
            self.connection.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.connection.close()

    def snapshot(self, user_id: str) -> tuple[int, dict[str, str]]:
        _identifier(user_id)
        row = self.connection.execute(
            "SELECT version, facts FROM profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return 0, {}
        try:
            facts = json.loads(row[1])
            if (type(row[0]) is not int or row[0] < 1 or not isinstance(facts, dict)
                    or not all(key in PREFERENCE_VALUES and isinstance(value, str)
                               and value in PREFERENCE_VALUES[key] for key, value in facts.items())):
                raise ValueError("Invalid profile data")
        except (ValueError, TypeError) as exc:
            raise ValueError("Stored profile is invalid; it was not overwritten") from exc
        return row[0], facts

    def _save(self, user_id: str, facts: dict[str, str]) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO profiles (user_id, version, facts) VALUES (?, 1, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET version = profiles.version + 1, facts = excluded.facts",
                (user_id, json.dumps(facts)),
            )

    def remember(self, user_id: str, key: str, value: str) -> None:
        if not isinstance(key, str) or key not in PREFERENCE_VALUES:
            raise ValueError("Supported memory keys: reply_style, preferred_language")
        if not isinstance(value, str) or value not in PREFERENCE_VALUES[key]:
            raise ValueError(f"Allowed {key} values: {', '.join(sorted(PREFERENCE_VALUES[key]))}")
        _, facts = self.snapshot(user_id)
        facts[key] = value
        self._save(user_id, facts)

    def forget(self, user_id: str, key: str) -> bool:
        if not isinstance(key, str) or key not in PREFERENCE_VALUES:
            raise ValueError("Supported memory keys: reply_style, preferred_language")
        _, facts = self.snapshot(user_id)
        if key not in facts:
            return False
        del facts[key]
        self._save(user_id, facts)
        return True


@dataclass
class MemoryResult:
    user_id: str
    session_id: str
    query: str
    response: str
    memory_action: str
    short_term_turns: int
    session_state: dict[str, str]
    long_term_facts: dict[str, str]


Responder = Callable[[str, dict], str]


def local_responder(query: str, context: dict) -> str:
    """Use supplied memory through a small deterministic support-reply template."""
    if query.lower().strip() == "what did i say last?":
        turns = context["recent_turns"]
        return f"Your previous chat message was: {turns[-1]['query']}" if turns else "There is no earlier chat turn in this session."
    issue = context["session_state"].get("current_issue")
    spanish = context["long_term_facts"].get("preferred_language") == "spanish"
    if not issue:
        return "Describe el problema con 'issue: ...'." if spanish else "Describe your support issue with 'issue: ...'."
    reply = f"Problema indicado: {issue}" if spanish else f"Reported issue: {issue}"
    if context["long_term_facts"].get("reply_style") != "concise":
        reply += "\nComparte el mensaje de error para investigarlo." if spanish else "\nPlease share the error message so support can investigate."
    return reply


def validate_turn(query: str, session: Session) -> None:
    if not isinstance(query, str) or not query.strip() or len(query) > 1000:
        raise ValueError("Query must contain text and be at most 1000 characters")
    if not isinstance(session, Session) or (session.user_id, session.session_id) != session._identity:
        raise ValueError("Session identity cannot change; create a new Session")
    if type(session.max_turns) is not int or not 1 <= session.max_turns <= 10:
        raise ValueError("max_turns must be an integer between 1 and 10")


def _sync_profile(session: Session, version: int) -> None:
    if session.profile_version != version:
        # Clear stale preference mentions, including other sessions on their next turn.
        session.history.clear()
        session.profile_version = version


def chat(query: str, session: Session, store: MemoryStore, *,
         responder: Responder = local_responder) -> MemoryResult:
    """Apply explicit memory controls locally; ordinary chat uses a bounded context.

    Responses are validated before committing the new chat turn/session issue.
    Preference updates invalidate recent history. Controls are not chat turns.
    """
    validate_turn(query, session)
    text = query.strip()
    version, facts = store.snapshot(session.user_id)
    _sync_profile(session, version)
    action = "chat"
    if text.lower() == "reset session":
        session.history.clear()
        session.state.clear()
        reply, action = "Session history and state cleared; saved preferences remain.", "session_reset"
    elif re.match(r"^(remember|recall|forget)\b", text, re.I):
        remember = re.fullmatch(r"remember\s+(\w+)\s*=\s*(\w+)", text, re.I)
        control = re.fullmatch(r"(recall|forget)\s+(\w+)", text, re.I)
        if remember:
            key, value = (item.lower() for item in remember.groups())
            store.remember(session.user_id, key, value)
            reply, action = f"Remembered {key}={value} for this user.", "remembered"
        elif control:
            command, key = (item.lower() for item in control.groups())
            if key not in PREFERENCE_VALUES:
                raise ValueError("Supported memory keys: reply_style, preferred_language")
            if command == "forget":
                removed = store.forget(session.user_id, key)
                reply = f"Forgot {key}." if removed else f"No saved {key} to forget."
                action = "forgotten"
            else:
                reply = f"Saved {key}={facts[key]}." if key in facts else f"No saved {key} for this user."
                action = "recalled"
        else:
            raise ValueError("Use 'remember key = value', 'recall key', or 'forget key'")
        version, facts = store.snapshot(session.user_id)
        _sync_profile(session, version)
    else:
        pending_state = deepcopy(session.state)
        if text.lower().startswith("issue:"):
            issue = text.split(":", 1)[1].strip()
            if not issue:
                raise ValueError("Provide text after 'issue:'")
            pending_state["current_issue"] = issue
            action = "session_issue_updated"
        context = {"user_id": session.user_id, "session_id": session.session_id,
                   "long_term_facts": facts, "session_state": pending_state,
                   "recent_turns": [asdict(turn) for turn in session.history[-session.max_turns:]]}
        reply = responder(text, deepcopy(context))
        if not isinstance(reply, str) or not reply.strip() or len(reply) > 4000:
            raise ValueError("Responder must return non-empty text of at most 4000 characters")
        reply = reply.strip()
        session.state = pending_state
        session.history.append(Turn(text, reply))
        del session.history[:-session.max_turns]
    return MemoryResult(session.user_id, session.session_id, query, reply, action,
                        len(session.history), deepcopy(session.state), dict(facts))


def main() -> None:
    # The runnable demos clean up their database; callers can choose a lasting path.
    with TemporaryDirectory() as directory, MemoryStore(Path(directory) / "memory.sqlite3") as store:
        session = Session("demo-user", "chat-1")
        results = [chat(query, session, store) for query in (
            "remember reply_style = concise", "issue: The app crashes during upload.",
            "What issue did I mention?",
        )]
        print(json.dumps([asdict(result) for result in results], indent=2))


if __name__ == "__main__":
    main()
