# Pattern 01: Prompt Chaining

Prompt Chaining is the idea of breaking one complex LLM task into a sequence of smaller, focused steps.

Instead of asking one giant prompt to do everything, we ask multiple simpler prompts (or functions) where each step improves, filters, or structures the output for the next one.

## What it is

Prompt Chaining is a **step-by-step workflow** where:
1. Step 1 transforms raw input (for example, summarize text)
2. Step 2 extracts useful signals (for example, themes or intent)
3. Step 3 produces a final, structured output

## Why it matters

- Improves reliability by narrowing what each step must do
- Makes debugging easier because each stage is inspectable
- Supports reuse (swap one step without rewriting everything)
- Enables gradual complexity as systems scale

## When to use it

Use Prompt Chaining when:
- A single prompt gives inconsistent or noisy results
- You need traceable intermediate outputs
- Tasks naturally break into sequential sub-tasks
- You want better control over output structure

## Advantages

- Clearer logic and maintainability
- Better testability (step-level unit tests)
- Easier observability and error handling
- Flexible enough for local simulation or real LLM backends

## Limitations

- More steps can increase latency
- Poorly designed step boundaries can propagate errors
- Requires extra design effort vs. one-shot prompting

## Real-world use cases

- Customer support triage: summarize ticket -> detect intent -> draft response
- Research workflows: summarize sources -> extract claims -> generate briefing
- Content ops: parse brief -> outline -> draft structured deliverables
- Internal copilots: rewrite request -> classify task -> produce action plan

## Simple Workflow

```text
Input
  |
  v
Step 1: Summarize
  |
  v
Step 2: Extract Themes
  |
  v
Step 3: Build Structured Response
  |
  v
Output
```

## Implementation Options

1. **Local no-API version (default)**
   - File: `app.py`
   - Uses deterministic local Python functions
   - Runs without API keys or network access

2. **Optional OpenAI-backed version**
   - Folder: `openai_version/`
   - Uses the official OpenAI Python SDK with `OPENAI_API_KEY`
   - Mirrors the same 3-step chain with real model calls

## Run

```bash
python app.py
python examples/basic_example.py
python examples/advanced_example.py
pytest
```
