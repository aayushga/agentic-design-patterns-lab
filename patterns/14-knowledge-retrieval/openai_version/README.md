# Optional OpenAI Retrieval-Augmented Generation

The host retrieves current fictional support-policy paragraphs locally, then uses
the official OpenAI Python SDK and Responses API to synthesize a cited answer.
No embedding API, hosted file-search service, file-upload endpoint, or vector database is used.
Only the selected evidence is included in the model request.

Default model: `gpt-6-astra` with low reasoning effort. Explicit Python `model=`
overrides `OPENAI_MODEL`, then the default. Overrides must support Responses,
structured outputs, and low reasoning effort.

## Setup and run

Python 3.10+; from the repository root in your virtual environment:

```bash
python -m pip install -r patterns/14-knowledge-retrieval/openai_version/requirements.txt
cp patterns/14-knowledge-retrieval/openai_version/.env.example patterns/14-knowledge-retrieval/openai_version/.env
# Edit the .env file with your own key, then export it:
set -a
source patterns/14-knowledge-retrieval/openai_version/.env
set +a
python patterns/14-knowledge-retrieval/openai_version/openai_rag.py
```

Scripts read exported variables; `.env` is not loaded automatically. Never commit
secrets. If relevant evidence is found but `OPENAI_API_KEY` is missing, the script
reports a clear error before creating a client.

**This optional script can incur API charges.** Each invocation makes at most one
model attempt, with a 30-second timeout and SDK retries disabled. Retrieval is
local and free. If no qualifying passage fits the evidence budget, the host
abstains without importing the SDK, requiring a key, or making a model request:

```bash
python patterns/14-knowledge-retrieval/openai_version/openai_rag.py --query "How do I reset my password?"
```

The parent-folder examples and offline tests always make zero live API calls.

## Evidence and output

The request contains the question plus a JSON list of selected passages, each
with chunk ID, document ID, title, revision, and exact indexed text. Archived
documents do not enter the index. The prompt treats query/source text as data,
instructs the model to ignore embedded directives, and prohibits facts beyond
the supplied evidence. Prompting is not a guarantee against malicious source
instructions; the tiny bundled corpus is host-controlled fictional data.

An illustrative model response is:

```json
{
  "status": "answered",
  "answer": "For fictional DemoDesk subscriptions, submit a refund request within 14 days of the charge date and include the invoice reference and charge date.",
  "citations": [
    {
      "chunk_id": "refunds-current:p1",
      "quote": "Refund requests for DemoDesk subscriptions must be submitted within 14 days of the charge date."
    }
  ]
}
```

This is illustrative, not a recorded live model result. The host checks that IDs
belong to the exact supplied context, that quotes are distinct exact excerpts,
and that a claimed answer has citations. Host metadata supplies the returned
titles and revisions. It does not automatically verify that every model claim
is supported by those quotations; valid citations alone do not establish factual
grounding. See the parent README for retrieval and semantic-validation limits.

The model may also decline despite receiving passages. It must then return
`insufficient_evidence` with empty answer/citations; the host supplies a fixed
abstention message. Failed, incomplete, refused, malformed, or invalidly cited
responses fail clearly without retrying or substituting an uncited model answer.
API failures propagate to the caller; the CLI prints a generic diagnostic.

The SDK client closes on success and failure. Requests use `store=False`; this
does not establish an account's retention policy. Selected fictional passages
are sent to the API when synthesis is requested.
No live model quality, latency, or account access was measured. No real account
lookup, refund, message, or other external action is performed.

Reference: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

Request safeguards: output is capped at 2500 tokens per attempt, response
storage is disabled (`store=False`), SDK retries are disabled, and clients close on
success or failure. SDK timeouts and cooperative application deadlines are not a
hard whole-run deadline. Token/request caps do not cap input charges or dollar spend.
