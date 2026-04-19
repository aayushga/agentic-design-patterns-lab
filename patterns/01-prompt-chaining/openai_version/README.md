# Optional OpenAI-Backed Prompt Chaining Version

This folder contains an **optional** implementation of Pattern 01 (Prompt Chaining) using the official OpenAI Python SDK.

The main local version in `../app.py` remains the default no-API implementation. This version is for users who want to run the same pattern with a real model.

## What it does

It runs a 3-step prompt chain:
1. Summarize input text
2. Extract key themes
3. Generate a final structured response

## Setup

1. Install dependencies (from the pattern folder):

```bash
pip install -r ../requirements.txt
```

2. Configure your API key:

```bash
cp .env.example .env
# then add your real key to OPENAI_API_KEY
```

3. Export the variable in your shell (example):

```bash
export OPENAI_API_KEY="your_api_key_here"
```

## Run

```bash
python openai_chain.py
```

## Notes

- No secrets are hard-coded.
- The script reads credentials from `OPENAI_API_KEY`.
- If the model returns malformed JSON for a step, the code includes lightweight fallbacks to keep the demo runnable.
