# OpenAI-backed Routing (Optional)

This folder provides an **optional** LLM-based variant of Pattern 02 Routing.

The main local implementation in `../app.py` remains the default no-API option.
Use this version when you want model-based intent classification.

## What it does

1. Accepts user input
2. Uses OpenAI to classify intent as one of:
   - `billing`
   - `support`
   - `sales`
   - `unknown`
3. Routes to the matching handler
4. Returns a structured response:
   - `original_query`
   - `selected_route`
   - `confidence`
   - `reason`
   - `handler_response`

## Setup

1. Install dependencies (from `patterns/02-routing`):

```bash
pip install -r requirements.txt
```

2. Create your environment file:

```bash
cp openai_version/.env.example openai_version/.env
```

3. Add your key to `.env` (or export directly):

```bash
export OPENAI_API_KEY="your_key_here"
```

## Run

```bash
cd patterns/02-routing
python openai_version/openai_router.py
```

## Safe fallback behavior

- If `OPENAI_API_KEY` is missing, the script prints a clear configuration error.
- If the model returns an invalid route, routing falls back to `unknown`.
