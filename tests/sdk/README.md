# Offline real-SDK contracts

These tests exercise all 21 optional OpenAI integrations using the installed
SDK's request serialization and response parsing with an in-memory HTTP transport.
Network sockets are blocked by the repository fixture. Credentials are fictional;
no live API endpoint, model access, or billable request is used.

From the repository root, with Python 3.11+:

```bash
python -m pip install 'openai>=2.32.0,<3' -r patterns/10-model-context-protocol/requirements.txt -r patterns/15-inter-agent-communication/requirements.txt
python -m pytest tests/sdk -q
```

The combined suite still works without the optional OpenAI SDK; this module skips
when it is absent. The MCP/A2A cases also require their separately installed SDKs.
CI explicitly runs the real-SDK contracts against the minimum and latest compatible
2.x versions. These tests cover HTTP payloads, bounded request options, tool-result
correlation, cleanup, and retry suppression. They do not establish live model
quality or account access, and are separate from API-free local examples.
