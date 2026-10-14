# Pattern 08: Memory Management

Memory lets an agent use information from earlier interactions. This original
exercise follows Chapter 8 of Antonio Gulli's *Agentic Design Patterns*, separating
three scopes in a small support-assistant demo:

| Scope | Example | Storage and lifetime |
| --- | --- | --- |
| Recent conversation | Last user queries and assistant replies | Bounded list in one `Session`; lost on restart |
| Session state | Current reported support issue | In-memory dictionary; survives history trimming, lost with the session |
| User preferences | Reply style and language | SQLite profile; available in new sessions and after reopening the database |

**New input → load this user's preferences → assemble session context → reply → retain a bounded turn**

Memory is supplied explicitly to the responder; it is not a change to model weights.
This example uses exact profile-key lookup, not vector search, RAG, automatic
summarization, or model-driven memory extraction. It focuses on session memory
and a small persistent semantic profile; episodic/procedural memory are beyond
this exercise.

## Free local run

Use Python 3.10 or newer. From the repository root:

```bash
python patterns/08-memory-management/app.py
python patterns/08-memory-management/examples/basic_example.py
python patterns/08-memory-management/examples/advanced_example.py
```

No SDK, API key, network, or API charges are needed. These demos create a temporary
SQLite file, demonstrate persistence by closing/reopening it, and clean it up on
exit. The Python API accepts a lasting path when you want preferences to survive
separate runs.

The local responder uses deterministic templates. It is not an LLM or a general
support agent. The saved style changes reply length; the saved language chooses
an English or Spanish support template. Memory-control acknowledgements and the
`What did I say last?` demonstration are in English.

## Basic output

```text
User: remember reply_style = concise
Assistant: Remembered reply_style=concise for this user.
Recent turns: 0
Session state: {}
Saved preferences: {'reply_style': 'concise'}

User: issue: The app crashes during upload.
Assistant: Reported issue: The app crashes during upload.
Recent turns: 1
Session state: {'current_issue': 'The app crashes during upload.'}
Saved preferences: {'reply_style': 'concise'}

User: What issue did I mention?
Assistant: Reported issue: The app crashes during upload.
Recent turns: 2
```

The next turn, `What did I say last?`, recalls the previous chat message. The
example's two-turn window stays at two by removing its oldest turn. The session
issue remains available even after its original message leaves that window.

## Advanced output

```text
After reopening: Saved reply_style=concise.
New session issue: Describe your support issue with 'issue: ...'.
Other user: No saved reply_style for this user.
Update: Remembered reply_style=detailed for this user.
Forget: Forgot reply_style.
After forgetting: No saved reply_style for this user.
Reset: Session history and state cleared; saved preferences remain.
Preferences after reset: Saved preferred_language=spanish.
```

A new session remembers the same user's saved preference, but not the previous
session's issue. A different user gets a different namespace. Updating a key
replaces its previous value; forgetting removes it from the profile. Session
reset clears chat history and session state while keeping saved preferences.

## Explicit controls

| Input | Effect |
| --- | --- |
| `remember reply_style = concise` | Save `concise` or `detailed` |
| `remember preferred_language = spanish` | Save `english` or `spanish` |
| `recall reply_style` | Read one saved preference |
| `forget reply_style` | Remove one saved preference |
| `reset session` | Clear this session's history and state |
| `issue: Upload fails.` | Set the current session issue and generate a reply |
| `What did I say last?` | Local demo: inspect the previous retained chat turn |

Only the two preference keys and listed values are supported. Ordinary chat never
implicitly writes long-term facts, and model output cannot update the profile.
Controls are local operations, not chat turns; they are not added to recent history.
A missing recall/forget reports that no value is saved. Malformed controls fail
before a responder or profile write is invoked.

Preferences have a version number. A changed version invalidates old chat turns
that could mention stale values. Other sessions notice that version on their
next interaction and clear their old turns before building context. The current
session issue is retained because it belongs to a separate scope. Forgetting
removes a preference, not every occurrence of that word in unrelated issue text,
external logs, or database backups.

## Python API and result

From the repository root, import with
`importlib.import_module("patterns.08-memory-management.app")`, then:

```python
with module.MemoryStore("patterns/08-memory-management/my-memory.sqlite3") as store:
    session = module.Session("alice", "chat-1", max_turns=3)
    result = module.chat("remember reply_style = concise", session, store)
    result = module.chat("issue: Upload fails.", session, store)
```

The result contains `user_id`, `session_id`, `query`, `response`, `memory_action`,
`short_term_turns`, `session_state`, and `long_term_facts`. Convert it with
`dataclasses.asdict` to inspect or serialize it. Returned state and facts are
copies. The responder receives a copied snapshot with the current user's
preferences, session state, and recent turns.

The window defaults to three turns and accepts one through ten. Inputs are limited
to 1000 characters and replies to 4000. This bounds stored text, not exact model
tokens. Trimming can remove useful details; no summary of removed turns is made.
Empty/failed/oversized replies do not commit a new chat turn or new session issue.
Database failures propagate; invalid profile data is not silently overwritten.
A session's identity cannot be rebound to another user or session ID.

SQLite writes use parameterized queries and committed transactions. This is a
single-threaded local demo without concurrent-writer conflict resolution. User
IDs are supplied by a trusted caller, not authenticated. The database is local
plaintext; it is not a secure vault. Use fictional preferences, and keep keys and
private data out of the demo. SQLite files under this pattern are ignored by Git;
an external database path needs its own handling.

## Optional OpenAI version and offline tests

[OpenAI setup](openai_version/README.md) generates replies using the same memory
snapshot. Controls remain free and work without a key or SDK; ordinary chat makes
one billable request. Default model: `gpt-6-astra`. The interactive CLI caps model
requests at five by default.

```bash
python -m pip install -r patterns/08-memory-management/requirements.txt
python -m pytest patterns/08-memory-management/tests -q
```

Tests cover persistence, scopes, bounded history, updates, forgetting, namespace
separation, failed-turn handling, request budgets, and SDK context construction.
They use temporary databases and fake SDK responses, blocking network connections.
No real SDK or API key is required.
