# Optional OpenAI Goal Setting and Monitoring

The official OpenAI Python SDK selects the next simulated action using the
Responses API and strict structured output. The fixed goal, action validation,
ticket updates, progress measurements, and stopping decisions remain local Python.

The default is `gpt-6-astra` with low reasoning effort. An explicit Python
`model=` argument overrides `OPENAI_MODEL`, which overrides the default. A model
override must support Responses, structured outputs, and low reasoning effort.

## Setup and run

Python 3.10+; from the repository root in your virtual environment:

```bash
python -m pip install -r patterns/11-goal-setting-and-monitoring/openai_version/requirements.txt
cp patterns/11-goal-setting-and-monitoring/openai_version/.env.example patterns/11-goal-setting-and-monitoring/openai_version/.env
# Edit that .env file with your own key, then export it:
set -a
source patterns/11-goal-setting-and-monitoring/openai_version/.env
set +a
python patterns/11-goal-setting-and-monitoring/openai_version/openai_goals.py
```

Scripts read exported variables; `.env` is not loaded automatically. Never commit
your key. Missing `OPENAI_API_KEY` produces a clear error before client creation.
An already completed goal returns locally without needing a key or SDK.

**Running this optional script makes billable model requests.** The free local
examples and offline tests in the parent folder do not. Default CLI limits are
six requests/actions and 120 seconds, with no SDK retries. A run can stop earlier
on success, two consecutive actions without progress, or an error:

```bash
python patterns/11-goal-setting-and-monitoring/openai_version/openai_goals.py --max-steps 3 --deadline-seconds 60
```

One request chooses one action; simulator execution and measurement cost nothing.
No separate judge request is made. Failures consume a request attempt and propagate;
they are not automatically retried. The SDK client closes on success or failure.
Requests use `store=False`; this does not imply any particular account retention
policy. The request timeout is the smaller of 30 seconds and the configured run
deadline. Deadline checks are cooperative: a request already in flight can overrun
the remaining total budget, but its action is not applied if selection finishes late.

## What to expect

The model receives the fixed goal, fictional queue, measured progress, and previous
action observations. It returns only:

```json
{"kind": "collect_context", "ticket_id": "T-101"}
```

The monitor applies the action, measures again, and sends that actual state to
the next request. With sensible choices, collecting T-101's missing context and
triaging T-101, T-102, and T-103 takes four requests. This is illustrative; model
choices and costs vary. The CLI prints the final structured result including
history, pending IDs, completion fraction, and stop reason. Non-completed runs
exit with code 1. Refusals, incomplete responses, malformed JSON, unsupported
actions, and out-of-goal ticket IDs fail clearly without claiming completion.

All data is fictional. No tickets, accounts, messages, files, or remote systems
are changed. Completion means the local triage goal was met, not a real customer
problem was solved. Validation uses fake responses; live model quality and account
access have not been measured.

Reference: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
