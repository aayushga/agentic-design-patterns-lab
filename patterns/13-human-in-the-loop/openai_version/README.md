# Optional OpenAI Human-in-the-Loop Drafting

The official OpenAI Python SDK generates a support-reply draft using Responses
and strict structured output. It can return only `draft`; it has no approval,
reviewer-selection, or dispatch capability. Python places the validated text into
the same pending-review queue as the free local example.

Default model: `gpt-6-astra` with low reasoning effort. Explicit Python `model=`
overrides `OPENAI_MODEL`, then the default. Overrides must support Responses,
structured outputs, and low reasoning effort.

## Setup and run

Python 3.10+; from the repository root in your virtual environment:

```bash
python -m pip install -r patterns/13-human-in-the-loop/openai_version/requirements.txt
cp patterns/13-human-in-the-loop/openai_version/.env.example patterns/13-human-in-the-loop/openai_version/.env
# Edit the .env file with your own key, then export it:
set -a
source patterns/13-human-in-the-loop/openai_version/.env
set +a
python patterns/13-human-in-the-loop/openai_version/openai_hitl.py --interactive
```

Scripts read exported variables; `.env` is not loaded automatically. Never commit
secrets. Missing `OPENAI_API_KEY` is reported before client creation. Empty/invalid
queries, invalid review windows, and full queues fail before a model request.

**This optional script can incur API charges.** Each invocation makes at most one
model attempt with a 30-second request timeout and SDK retries disabled. Failed,
incomplete, refused, empty, malformed, or oversized output does not create a
review or retry automatically. Human edits and decisions make no model requests.
The free parent-folder demos and all tests make no live API calls.

Without `--interactive`, the script generates one draft, prints a pending-review
JSON object and empty outbox, then exits without approving anything. In-memory
state is discarded on exit; it cannot be resumed in another invocation. Use the
interactive flag to draft and review within the same process.

## Expected interaction

```text
Optional demo: at most one billable model attempt; human review actions are local.
Review: pending | revision 1
Customer query: I was charged twice for my subscription. Can you help?
Draft for human review: [model-generated draft, which may vary]
Decision [approve/edit/reject/quit]: edit
Replacement draft: Please share the invoice reference and charge dates for review.
Review: pending | revision 2
Draft for human review: Please share the invoice reference and charge dates for review.
Decision [approve/edit/reject/quit]: approve
Approved revision added to simulated outbox. No real message was sent.
```

This is an illustrative interaction, not a recorded live model run. The final
JSON records decisions and revision state. The review deadline defaults to five
minutes starting after successful draft submission; `--review-seconds 60` changes
it. A late decision is rejected, although terminal input itself is not forcibly
interrupted. Rejection, quitting, and EOF never implicitly approve.

Generation is not verification. A model draft may be factually wrong or claim
approval in its text; that text remains data and cannot change queue state. Extra
JSON fields such as `state` or `reviewer` are rejected. A person must examine the
draft before approving it. Human edits also require approval of their new revision.

The SDK client closes on success and failure. Requests use `store=False`; this
does not establish an account's retention policy. No live model quality, account
access, or latency was measured. All dispatch is simulated in memory: no message
provider, recipient address, actual customer record, or external write is present.
Reviewer labels are not authentication; see the parent README's scope limits.

Reference: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

Request safeguards: output is capped at 1500 tokens per attempt, response
storage is disabled (`store=False`), SDK retries are disabled, and clients close on
success or failure. SDK timeouts and cooperative application deadlines are not a
hard whole-run deadline. Token/request caps do not cap input charges or dollar spend.
