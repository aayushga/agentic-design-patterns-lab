# Pattern 13: Human-in-the-Loop

An agent prepares work, a person reviews it, and the workflow resumes only with
that person's decision. This original exercise follows Chapter 13 of Antonio
Gulli's *Agentic Design Patterns*, using support-reply drafts and a simulated outbox.

**Draft → pending review → human approves, edits, or rejects → dispatch approved revision**

The escalation policy is deliberately simple: **every draft requires human
approval**. A model's confidence, a sentence claiming approval, or a successful
generation cannot replace that decision. No real email, chat, support ticket,
or account is accessed or changed by this example.

## Free local run

Python 3.10+; the local implementation uses only the standard library. From the
repository root:

```bash
python patterns/13-human-in-the-loop/app.py
python patterns/13-human-in-the-loop/examples/basic_example.py
python patterns/13-human-in-the-loop/examples/advanced_example.py
```

No API key, SDK, network connection, or API charge is needed. The default `app.py`
prints a pending review as JSON and an empty simulated outbox, then exits. It never
approves automatically. Both example scripts label their reviewer decisions as
scripted, so CI can demonstrate the workflow without asking a person for input.

### Try the human role yourself

```bash
python patterns/13-human-in-the-loop/app.py --interactive
```

You see the customer query, exact draft, and current revision, followed by:

```text
Decision [approve/edit/reject/quit]:
```

- `approve`: approve the displayed revision and add its exact text to the simulated outbox.
- `edit`: enter replacement text; a new pending revision is displayed for review.
- `reject`: end the review without dispatch.
- `quit`, EOF, or interruption: stop without treating silence as approval.

State exists only in that Python process. Exiting discards it; a later run creates
a new review, rather than resuming the previous one. Use `--interactive` at startup
to draft and review in one session. No text is actually sent, even after approval.

## Basic example

```text
SCRIPTED REVIEWER DEMO
Review: pending | revision 1
Customer query: I was charged twice for my subscription. Can you help?
Draft for human review: Thanks for reporting the issue. Please share the relevant
reference and details so support can review it. No account has been checked or changed.
Dispatch blocked: Operation is not permitted while review is pending
Scripted decision: approve revision 1
State: dispatched
Simulated outbox entries: 1
```

The wrapped draft above is reformatted for readability. The first dispatch attempt
is deliberately blocked. Only the explicitly scripted approval permits the second.
The interactive mode uses actual terminal input instead of scripted decisions.

## Advanced example

```text
After edit: revision 2, state pending, approval None
Old approval blocked: Stale revision; review the latest draft before acting
New draft still needs approval: Operation is not permitted while review is pending
Dispatched approved revision: 2
Duplicate blocked: Operation is not permitted while review is dispatched

Rejected draft blocked: Operation is not permitted while review is rejected
Expired approval blocked: Operation is not permitted while review is expired
Simulated outbox entries: 1 | expired queue: 0
```

This excerpt is shortened. The example approves revision 1, edits it, then proves
that approval cannot authorize revision 2. The corrected text needs a fresh
decision. Separate scenarios demonstrate rejection and expiry with a simulated
clock, without sleeping.

## Review state and audit history

| State | Permitted next action |
| --- | --- |
| `pending` | Edit, approve, or reject before expiry |
| `approved` | Dispatch the approved revision, edit and clear approval, or reject |
| `dispatched` | Terminal; another dispatch or edit is blocked |
| `rejected` | Terminal; create a separate review to submit new work |
| `expired` | Terminal; a late approval or dispatch is blocked |

Every modifying call includes the expected revision. The queue checks the current
record rather than trusting a caller's old snapshot. Editing increments the
revision and clears approval/reviewer fields without extending the deadline.
Approval stores its revision, and dispatch checks that it still matches.

Frozen review, audit, and delivery records prevent accidental mutation through
returned objects. Outbox access returns a tuple. Audit events record the action,
revision, actor label, and note; delivery retains the exact approved text and reviewer.
The default queue holds at most 20 reviews across its lifetime, including terminal
ones, and permits at most five revisions per review.

The review window defaults to 300 seconds and starts at submission, after a draft
is ready. `expires_at` is a process-local monotonic-clock value, not a wall-clock
timestamp. Expiry is checked when reading or acting on a review. Terminal input
can remain blocked beyond the window, but a late decision cannot authorize dispatch.
There is no background timer, notification, or persistent queue.

## Scope and relation to earlier patterns

This is a single-process, single-thread teaching example. Reviewer labels are
audit data supplied by a trusted local caller, not authenticated identities.
The code demonstrates workflow control, not a secure remote approval service.
Real multi-user deployments would need authenticated reviewer permissions,
durable state, and atomic version/dispatch handling across workers and restarts.
Approval records a person's choice; it does not establish that the text is correct.

Pattern 09 uses feedback to adapt an application policy. Here a human decision
controls whether an action may proceed. Pattern 12 can report that human review
is needed; Pattern 13 actually pauses for a decision and resumes through a versioned
gate. The book's ADK escalation example inspires the handoff, while this exercise
implements the review and resume path directly in Python.

## Optional OpenAI version and offline tests

See [OpenAI setup](openai_version/README.md). Astra drafts text; human decisions
use the same local queue and cannot be delegated to the model.

```bash
python -m pip install -r patterns/13-human-in-the-loop/requirements.txt
python -m pytest patterns/13-human-in-the-loop/tests -q
```

Offline tests cover revision-bound approval, edits, rejection/revocation, expiry,
duplicate dispatch, queue bounds, immutable snapshots, actual interactive command
handling, and fake model outputs/errors. Tests block network connections and need
neither an OpenAI SDK installation nor an API key.
