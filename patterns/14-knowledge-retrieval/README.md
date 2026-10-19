# Pattern 14: Knowledge Retrieval (RAG)

Retrieve relevant source passages before preparing an answer, and keep citations
so a reader can inspect the evidence. This original exercise follows Chapter 14
of Antonio Gulli's *Agentic Design Patterns* using fictional DemoDesk support policies.

**Documents → paragraph chunks → index → retrieve → bounded context → answer with citations**

The free version retrieves passages and presents exact excerpts. It is an
extractive reference pipeline, using a deterministic stand-in for generation.
The optional OpenAI version completes the RAG flow by asking Astra to synthesize
only the retrieved context. Neither version downloads models, computes paid
embeddings, or needs a vector database.

## Knowledge base and retrieval

`knowledge_base/support_policies.json` contains five small documents: current
refund, cancellation, duplicate-charge, and upload policies, plus an archived
refund policy. These are invented learning fixtures, not real product terms.

Only documents explicitly marked `current` enter the index. The current refund
policy says 14 days, while the excluded archived version says 30 days. This is
host-owned metadata filtering, not an LLM deciding which policy to trust. No
clock-based freshness detection or automatic reconciliation is performed.

Each non-empty paragraph becomes one chunk, with whitespace normalized and a
stable ID such as `refunds-current:p1`. Titles and revisions travel with it.
Paragraphs must fit the 600-character demo limit; longer sources need explicit
chunking before being added, rather than silent truncation.

The retriever uses a small standard-library implementation of **BM25 keyword
ranking**, with `k1=1.5`, `b=0.75`, and positive inverse-document-frequency weights.
It uses lowercased English word tokens, a short stop-word list, and a simple
plural rule. At least two distinct query terms must match, or one for a one-term
query. Scores must also meet `min_score` (default 0.5).

This is lexical retrieval, not semantic embedding search. It can miss paraphrases,
and keyword overlap does not establish relevance or complete coverage of a
multi-part question. Ranking scores are not confidence probabilities. Thresholds
are illustrative and depend on corpus size; they have not been calibrated as a
production relevance measure.

Up to three passages are selected by default, sorted by score with chunk-ID tie
breaking. The JSON-serialized evidence, including metadata, must fit a default
2,500-character budget. The retriever skips chunks that do not fit, preserving
whole passages. This limits evidence characters, not total prompt tokens. No
qualifying evidence produces `insufficient_evidence` instead of an invented answer.

## Free local run

Python 3.10+; local code uses only the standard library. From the repository root:

```bash
python patterns/14-knowledge-retrieval/app.py
python patterns/14-knowledge-retrieval/examples/basic_example.py
python patterns/14-knowledge-retrieval/examples/advanced_example.py
python patterns/14-knowledge-retrieval/app.py --query "How do I reset my password?"
```

No SDK, API key, network connection, or API charge is needed. Paths are resolved
relative to the implementation, so launching the script from another working
directory still finds the supplied knowledge base.

### Basic example

```text
Question: Within how many days can I request a refund?
Retrieved: ['refunds-current:p1 (3.455)']
Status: answered
Relevant excerpts from the fictional policies:
- Refund requests for DemoDesk subscriptions must be submitted within 14 days of the charge date. Include the invoice reference and charge date.
Source [refunds-current:p1] revision 2: Refund policy (fictional DemoDesk)
Fictional policies only; no real account lookup or action.
```

The basic example selects only the top passage. `app.py` prints structured JSON
with the original question, answer status, evidence quotes, source metadata,
retrieved passages/scores, and generator label.

### Advanced example

```text
Excluded archived documents: ['refunds-archived']

Question: What invoice reference and charge dates are needed for duplicate charges and refund requests?
Retrieved: ['refunds-current:p1 (7.066)', 'duplicate-charges:p1 (6.910)']
Status: answered
[exact excerpts from both policies, followed by their citations]

Question: Does cancellation automatically refund earlier charges?
Retrieved: ['cancellation:p2 (7.932)']
Status: answered
[excerpt explaining that cancellation does not automatically refund earlier charges]

Question: How do I reset my password?
Retrieved: []
Status: insufficient_evidence
I could not find enough supporting evidence in the fictional DemoDesk knowledge base to answer this question.
```

This excerpt is shortened. The advanced example varies `top_k` for the multi-source
and focused questions. The password question has no qualifying evidence in this
fixture; abstention does not prove that a differently worded answer could never
exist in another source or be missed by a lexical retriever.

## Citations and limits

Both versions validate answer structure and citations against the **actual supplied
chunks**, not the whole corpus. Every accepted answer needs 1–5 citations with
distinct exact excerpts. IDs from archived, invented, or unselected chunks are
rejected. The host supplies titles and revisions; the model cannot invent them.
Abstention uses a fixed message and no citations.

The local answer copies retrieved paragraphs, while the optional model writes
new prose. Citation membership and exact-quote checks do **not** prove that a
model's claim follows from its sources, that all claims are cited, or that the
documents are true and mutually consistent. Human inspection or additional
grounding evaluation is still needed for semantic correctness. `answered` means
an output passed this example's checks; the local output is explicitly an excerpt
list, not a guarantee that every part of a question was resolved.

The file read is bounded to 100,000 bytes, with at most 20 documents, 100 current
chunks, and 5 selected passages. Loading/chunking rejects malformed records,
duplicate document IDs, oversized paragraphs, and invalid retrieval limits.
There is no user-account access, permission filtering, live internet search,
GraphRAG, model training, or external write. Host-selected files are trusted local
inputs; the model cannot choose paths or execute source content.

Pattern 08 stores conversation context and preferences. Here the application
searches an external-to-the-model document collection. Pattern 10 standardizes
tool/server access; this example performs retrieval directly inside the host.
The chapter also covers semantic, hybrid, graph, and agentic retrieval. Those are
extensions beyond this small, inspectable lexical baseline.

## Optional OpenAI version and offline tests

See [OpenAI setup](openai_version/README.md) for one bounded synthesis request.

```bash
python -m pip install -r patterns/14-knowledge-retrieval/requirements.txt
python -m pytest patterns/14-knowledge-retrieval/tests -q
```

Tests cover retrieval relevance, metadata filtering, source updates, deterministic
ranking, bounded context, abstention, citation provenance, invalid model output,
API failure, and cleanup. Model responses are faked and network connections are
blocked. No OpenAI SDK or API key is required for tests.

References: [BM25 similarity and inverse document frequency](https://lucene.apache.org/core/10_2_2/core/org/apache/lucene/search/similarities/BM25Similarity.html),
[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
