# Optional OpenAI-Backed Prompt Chaining

The default [local implementation](../app.py) runs without an API key or OpenAI SDK.
This optional version uses the official SDK, Responses API, and `gpt-6-astra`.

## What It Does

Runs three dependent model calls: summarize input, extract themes, and generate a
structured response. Each step receives the preceding step's result.

The result includes `summary`, `themes`, and `final_response`. The final response
keeps `input_length`, `summary`, and `themes` from the known chain state and adds
`recommended_next_step`.

## Setup and Run

Use Python 3.10 or newer. Start from the repository root with your virtual environment active:

```bash
cd patterns/01-prompt-chaining
python -m pip install -r openai_version/requirements.txt
cp openai_version/.env.example openai_version/.env
```

Edit `openai_version/.env` locally, replacing the placeholder with your real API key.
Then load it into your shell and run the example (macOS/Linux, bash or zsh):

```bash
set -a
source openai_version/.env
set +a
python openai_version/openai_chain.py
```

The scripts read **exported environment variables**; copying or editing `.env`
alone does not load it. Alternatively, export `OPENAI_API_KEY` and `OPENAI_MODEL`
directly in your shell. `.env` is Git-ignored; never commit a real key.

## Model Configuration

`OPENAI_MODEL` defaults to `gpt-6-astra` when unset or blank. A Python `model=`
argument overrides the environment. Requests use `reasoning={"effort": "low"}`
and omit temperature, following [OpenAI's migration guidance](https://developers.openai.com/api/docs/guides/latest-model).
Choose an override that supports Responses and low reasoning effort; Routing
also needs structured outputs. You need API access to your selected model, and live
runs incur API usage charges. This example is validated offline, not against a live model.

## Failure Behavior

- Missing or blank `OPENAI_API_KEY`: clear configuration error.
- Blank input: rejected before any API request.
- Malformed theme output: falls back to `["general"]`.
- Malformed final output: preserves known fields and provides a safe review recommendation.
- Empty, refused, or incomplete step: stops the chain with an error rather than passing bad data onward.
- API/network errors: propagate to Python callers; the CLI reports a failure and exits nonzero.

## Offline Tests

From this pattern folder:

```bash
python -m pip install -r requirements.txt
python -m pytest
```

Tests mock the SDK, verify model selection and output handling, and block network
connections. They run without the SDK or a real API key.
