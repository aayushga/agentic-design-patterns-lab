# Optional OpenAI Memory

The official OpenAI Python SDK generates replies from an application-managed
memory snapshot: saved preferences, current session state, and bounded recent
conversation turns. This follows the [conversation-state guide](https://developers.openai.com/api/docs/guides/conversation-state)
by supplying context explicitly rather than relying on the model to remember it.

Each call is a fresh Responses request with text data in a JSON payload. It does
not continue a previous response or replay its hidden reasoning. Recent turns
are application notes, not raw SDK output items. `store=False` disables storage
of the Response object; it does not mean the supplied context stays on your Mac
or guarantee zero data retention. Ordinary chat sends that context to OpenAI.

The [local version](../README.md) demonstrates memory without API charges.

## Setup and interactive run

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r patterns/08-memory-management/openai_version/requirements.txt
read -s "OPENAI_API_KEY?OpenAI API key: "; echo
export OPENAI_API_KEY
export OPENAI_MODEL=gpt-6-astra
python patterns/08-memory-management/openai_version/openai_memory.py --user-id demo-user
```

The key entry uses macOS's default zsh. Never commit a real key. `.env.example`
contains placeholders; the script reads exported variables without automatically
loading `.env` files.

The default model is `gpt-6-astra` with low reasoning effort. `OPENAI_MODEL`
overrides it; an explicit `model=` argument takes precedence. The chosen model
must support Responses and low reasoning effort and be available to your account.

Try:

```text
remember reply_style = concise
issue: The app crashes during upload.
What issue did I mention?
recall reply_style
forget reply_style
reset session
quit
```

`remember`, `recall`, `forget`, and `reset session` run entirely locally, even
without an installed SDK or API key. Ordinary chat, including `issue: ...`, makes
one billable model request. It does not perform support actions or send a reply
to anyone. Exact reply wording and preference adherence can vary.

## Persistence, budget, and failures

The interactive CLI uses `openai_version/memory.sqlite3` by default, keeping
explicit preferences between runs. It prints the database path and starts a
fresh session each run. Use `--db /your/chosen/path/memory.sqlite3` to select a
path whose parent already exists. Use the same trusted `--user-id` to retrieve
that user's preferences. The IDs are namespaces, not login credentials.

The CLI allows **at most five model request attempts per run**. Change this with
`--max-requests N`, accepting integers one through twenty. Failed attempts count;
automatic SDK retries are disabled. After exhaustion, local memory controls
still work. Each model call has a 30-second SDK timeout and a client that closes
on success or failure. There are no automatic memory-extraction or summary calls.

Missing keys, SDK/API failures, incomplete responses, empty text/refusals, and
oversized replies fail without committing a new chat turn or issue. Existing
memory stays available. Profile-change synchronization can still clear stale
history before an attempted reply. Stored profile errors are surfaced rather
than erased or replaced. SQLite connections close when the demo exits.

Instructions treat memory as data, restrict claims to supplied context, and ask
for style/language preferences to be respected. These are not guarantees against
prompt injection or invented recollections. The application controls memory
writes; the model can generate only text, not persistence commands.

## Python usage

```python
import importlib

local = importlib.import_module("patterns.08-memory-management.app")
optional = importlib.import_module(
    "patterns.08-memory-management.openai_version.openai_memory"
)
responder = optional.OpenAIResponder(max_requests=2)
with local.MemoryStore("patterns/08-memory-management/my-memory.sqlite3") as store:
    session = local.Session("demo-user", "chat-1")
    # Local operation: no API call.
    optional.run_openai_turn("remember reply_style = concise", session, store,
                             responder=responder)
    # Billable: one model request with the retrieved preference and session context.
    result = optional.run_openai_turn("issue: Upload fails.", session, store,
                                     responder=responder)
```

Reuse one responder to retain its request budget across turns. Without a shared
responder, `run_openai_turn` creates a one-request responder for that call, so
limits do not carry between calls. Set `model=` on the shared responder, or on
`run_openai_turn` when no responder is supplied; passing both is rejected.

See the local README for supported preference values, forgetting behavior, session
reset, and storage limitations. Tests use temporary databases, fake SDK responses,
and blocked network connections, with no real SDK, key, or API charges. They
validate memory delivery and orchestration, not live model quality or account access.

Request safeguards: output is capped at 2000 tokens per attempt, response
storage is disabled (`store=False`), SDK retries are disabled, and clients close on
success or failure. SDK timeouts and cooperative application deadlines are not a
hard whole-run deadline. Token/request caps do not cap input charges or dollar spend.
