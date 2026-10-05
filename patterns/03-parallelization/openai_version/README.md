# Optional OpenAI Parallelization

The default [local implementation](../app.py) is free to run. This optional version
makes up to **three billable OpenAI API requests** for one support ticket:
summary, keywords, and urgency. They run concurrently using `AsyncOpenAI` and the
Responses API. The final merge is local Python and makes no fourth model request.

## Setup and Run

Use Python 3.10 or newer. From the repository root, with your virtual environment active:

```bash
cd patterns/03-parallelization
python -m pip install -r openai_version/requirements.txt
cp openai_version/.env.example openai_version/.env
```

Edit `.env` locally, replacing the API-key placeholder. Load it into bash or zsh:

```bash
set -a
source openai_version/.env
set +a
python openai_version/openai_parallel.py
```

Scripts read exported environment variables and do not automatically load `.env`.
The default model is `gpt-6-astra` with low reasoning effort, matching the existing
optional patterns. Set `OPENAI_MODEL=gpt-6.1-sol` for an alternative, or pass `model=`
to `run_openai_parallel` (it takes precedence). Overrides must support Responses and
low reasoning effort. API access and billing are separate from the model setting
used to write code in Codex.

## Output and Failure Handling

The output has the same structure as the local example: `original_query`,
`task_results`, `combined_response`, and `elapsed_seconds`. Model outputs are plain
text; urgency labels are not calibrated probabilities. The merge only includes
successful branch text and explicitly labels unavailable analyses.

- A missing or blank API key produces a clear configuration error.
- Empty input is rejected before creating the client.
- Empty/refused/incomplete responses or API exceptions become individual task errors.
- Requests have a 30-second per-task timeout; successful branches are retained if another fails.
- SDK retries are disabled to avoid unexpected extra requests.
- The async client is closed after completion or cancellation.
- The CLI prints partial results and exits nonzero when any analysis is unavailable.

Timeout/cancellation stops waiting for a request locally; it does not guarantee that
server processing or API charges stop. Running concurrently changes latency, not the
number of requests. No live API requests were made to validate this implementation.

## Offline Tests

From `patterns/03-parallelization`:

```bash
python -m pip install -r requirements.txt
python -m pytest
```

Tests install a fake async SDK, verify all three calls overlap, and check model
selection, timeout handling, and client cleanup. The real SDK and an API key are
not needed. Use the local examples to explore the pattern without API costs.

References: [official Python SDK](https://github.com/openai/openai-python),
[OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model).
