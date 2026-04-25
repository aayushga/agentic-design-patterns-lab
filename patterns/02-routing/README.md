# Pattern 02: Routing

Routing is the idea of sending an input to the **right handler** based on the input's intent.

Instead of one giant function trying to answer everything, we first detect what the user wants, then route to a specialized handler.

## What it is

Routing is a control pattern with two core steps:
1. **Intent detection** (figure out what kind of request we have)
2. **Route selection** (send the request to the best matching handler)

For this pattern, we use local Python logic (keyword matching) so it is easy to run, inspect, and test.

## Why it matters

- Keeps logic clean and modular
- Improves response quality by using focused handlers
- Makes systems easier to scale (add routes without rewriting everything)
- Simplifies debugging because you can inspect route decisions

## When to use it

Use Routing when:
- You have multiple request types (billing, support, sales, etc.)
- Different request types need different processing rules
- You want predictable behavior before adding complex models
- You need traceable decision paths for testing and audits

## Advantages

- Simple architecture that is easy to understand
- Better separation of concerns
- Deterministic and testable local behavior
- Smooth path to future model-based intent detection

## Limitations

- Rule-based routing can miss nuanced intent
- Keyword overlap can cause ambiguous results
- Requires maintenance as domains and language evolve

## Real-world use cases

- Support ticket triage (billing vs technical support)
- Chatbot message dispatching
- Email inbox classification and forwarding
- Lead qualification workflows (sales vs support)
- Internal helpdesk routing to the right team

## Simple Workflow

```text
Input -> Intent Detection -> Route Selection -> Handler -> Output
```

## Run

```bash
python app.py
python examples/basic_example.py
python examples/advanced_example.py
pytest tests/test_routing.py
```
