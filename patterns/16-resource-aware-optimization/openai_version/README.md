# Optional OpenAI backend for resource-aware responses

The host chooses economy or thorough **before** a request and reserves its output
allowance. The official OpenAI SDK generates plain support-guidance text using
Responses. The host validates it and returns the same structured result as the
free local version. No tools, web search, account access, or hidden router calls run.

## Setup

Python 3.10+; from the repository root:

```bash
python -m pip install --only-binary=:all: -r patterns/16-resource-aware-optimization/openai_version/requirements.txt
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="gpt-6-astra"
python patterns/16-resource-aware-optimization/openai_version/openai_optimizer.py
```

Missing `OPENAI_API_KEY` produces a clear error before importing/creating the SDK
client. `.env.example` documents the settings; scripts do not automatically load `.env`.
Use fictional queries; the query and chosen detail are sent to the provider.

The default CLI requests a detailed response with a 2200-output-token allowance,
two-call limit, and a 30-second cooperative session deadline. For a smaller allowance:

```bash
python patterns/16-resource-aware-optimization/openai_version/openai_optimizer.py --output-budget 600
```

This skips thorough and attempts a brief economy response, labeled `degraded`.
Add `--require-detail` to block instead of downgrading. Use `--detail brief` when a
brief response is the original requirement. `--max-calls` and `--seconds` set the
shared session limits. No eligible profile means no API request.

## Models and caps

Both profiles preserve the lab's Astra default. Economy uses `low` effort and a
600-output-token cap; thorough uses `medium` and 1600. An explicit
`openai_agent(model=...)` overrides `OPENAI_MODEL`, which overrides `gpt-6-astra`.
For economy, explicit `economy_model=` overrides `OPENAI_ECONOMY_MODEL`, which
otherwise inherits the selected main model. Overrides must support Responses and
the chosen reasoning effort. For an optional different economy model, set:

```bash
export OPENAI_ECONOMY_MODEL="gpt-6-luna"
```

Model access depends on the account. The [official deployment guidance](https://developers.openai.com/api/docs/guides/deployment-checklist)
describes effort tuning and efficient models, including Luna. These demo profiles
are an application policy, not a measured quality or latency comparison.

**API usage is billable.** A brief query makes at most one model attempt; a detailed
query makes at most two, subject to remaining allowances. Known transient connection,
server, or explicitly classified rate-limit failures can fall back from thorough to
economy. Authentication, permission, quota/ambiguous 429, invalid request, incomplete
output, and invalid answer failures stop without another paid attempt. SDK retries
are disabled. Failed HTTP-success responses are classified by their safe error code.

Reservations remain consumed after every attempted request. They are **not actual
usage or dollar spending**: input tokens also cost money, and timeouts can still
incur charges. `max_output_tokens` bounds generated tokens, including reasoning;
small caps can produce incomplete responses or no visible answer. The host does
not return partial output as success or automatically increase the cap. See the
[official reasoning and output-limit guidance](https://developers.openai.com/api/docs/guides/reasoning).

The SDK client uses a 30-second timeout, with each request receiving the smaller
remaining session time, and closes on context exit. `store=False` is set. Cache
hits make no new request; this is the application's local cache, not provider prompt
caching. Avoid sharing a session across concurrent callers or changing its model
configuration while its cache exists.

All tests run with fake SDK responses. They do not measure live answer quality,
latency, account access, or actual costs. You can learn the pattern using only the
free local implementation and its examples.
