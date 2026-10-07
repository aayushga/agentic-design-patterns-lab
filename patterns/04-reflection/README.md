# Pattern 04: Reflection

Reflection improves a draft through feedback: **draft → critique → revise → critique
again**. A producer creates an answer, a critic checks it against explicit criteria,
and the producer uses that feedback to revise it. The loop stops when the critic
approves, the revision budget is exhausted, or drafts repeat.

This chapter follows Reflection in Antonio Gulli's *Agentic Design Patterns*.
The implementation is an original, simplified support-reply exercise.

## How this differs from the earlier patterns

| Pattern | Flow |
| --- | --- |
| Prompt Chaining | Each stage transforms the previous stage's output in a fixed sequence. |
| Routing | A decision selects a handler. |
| Parallelization | Independent analyses run concurrently, then merge. |
| Reflection | Feedback determines whether to revise a draft and check it again. |

Reflection can help with writing, code review, and quality checks where clear
criteria exist. It adds time and, with an API, cost. Critic approval means the
reply meets the selected rubric; it does not guarantee factual correctness.

## Free local version

From the repository root, using Python 3.10 or newer:

```bash
python patterns/04-reflection/app.py
python patterns/04-reflection/examples/basic_example.py
python patterns/04-reflection/examples/advanced_example.py
```

No SDK, API key, or network is needed. The producer deliberately starts with
an incomplete reply, the critic uses transparent rules, and the reviser applies
named feedback. For the ticket “I was charged twice for my subscription.”:

- Initial draft: “We received your request.”
- Critique: add a courteous acknowledgement, mention the issue, and ask for details.
- Revised reply: 'Thank you for contacting support. We received your request.
  You reported: "I was charged twice for my subscription." Please share the
  relevant invoice number or error message so we can investigate.'
- Final critique: approved, after one revision.

The local rubric checks for “thank you,” the original issue, “please share,”
a maximum of 80 words, and a few unsupported promise keywords. Customer text in
the generated `You reported: "..."` quotation is excluded from the promise check.
These rules illustrate the feedback loop; they are not semantic understanding
or a production support policy. A long ticket can remain unapproved because
quoting it exceeds the word limit.

## Inspecting the result

`run_reflection(query)` returns a dataclass that can be converted with
`dataclasses.asdict`:

| Field | Meaning |
| --- | --- |
| `original_query` | Customer's ticket |
| `initial_draft` | First reply, generated or supplied |
| `final_draft` | Last reviewed reply |
| `approved` | Whether its critic found no unresolved issues |
| `revisions` | Number of accepted revisions after the initial draft |
| `stop_reason` | `approved`, `revision_limit`, or `no_progress` |
| `history` | Every reviewed draft, revision number, approval, and issues |

The default budget is two revisions; callers can choose an integer from zero
to five. Zero still reviews the initial draft. Every accepted revision is
reviewed, including the last allowed revision. Repeated drafts, ignoring
whitespace differences, stop the loop without accepting the repeated candidate.
An unapproved final draft retains its issues for human review.

You can supply `initial_draft=` or replace the `producer`, `reviewer`, and
`reviser` callbacks. Reviewers return `Critique(approved=..., issues=[...])`.
Approval must agree with the issues: approved replies have an empty list.
Malformed feedback, empty stage outputs, and stage exceptions fail explicitly.

## Optional OpenAI version

[Setup and cost details](openai_version/README.md). This uses the official SDK,
separate writer and critic prompts, structured critic output, and the same
bounded reflection loop. The default model is `gpt-6-astra`; model selection
is configurable. It makes live, billable requests only when you run that version.

## Offline tests

```bash
python -m pip install -r patterns/04-reflection/requirements.txt
python -m pytest patterns/04-reflection/tests -q
```

Tests cover feedback delivery, final reviews, early approval, budget exhaustion,
repeated drafts, malformed critiques, missing keys, API errors, and model
selection. SDK calls are replaced with fakes; network connections are blocked.
The real OpenAI package is not needed to run the suite.
