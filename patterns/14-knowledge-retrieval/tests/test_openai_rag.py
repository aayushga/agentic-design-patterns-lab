"""Only selected evidence reaches the model; all requests are faked offline."""
import importlib
import json
import sys
from types import SimpleNamespace as NS

import pytest

module = importlib.import_module("patterns.14-knowledge-retrieval.openai_version.openai_rag")
app = importlib.import_module("patterns.14-knowledge-retrieval.app")
QUESTION = "Within how many days can I request a refund?"


def output(chunk_id="refunds-current:p1", quote=None):
    quote = quote if quote is not None else app.KnowledgeBase(app.load_documents()).retrieve(QUESTION, top_k=1)[0].chunk.text
    return json.dumps({"status": "answered", "answer": "In this fictional policy, request a refund within 14 days of the charge date.",
                       "citations": [{"chunk_id": chunk_id, "quote": quote}]})


@pytest.fixture
def sdk(monkeypatch):
    def install(raw=None, *, status="completed", error=None):
        requests, clients = [], []
        class Client:
            def __init__(self, **kwargs):
                self.state = {"options": kwargs, "closed": False}
                clients.append(self.state)
                self.responses = NS(create=self.create)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.state["closed"] = True
            def create(self, **kwargs):
                requests.append(kwargs)
                if error:
                    raise error
                return NS(status=status, output_text=raw)
        monkeypatch.setitem(sys.modules, "openai", NS(OpenAI=Client))
        monkeypatch.setenv("OPENAI_API_KEY", "offline-placeholder")
        return requests, clients
    return install


def test_only_retrieved_bounded_current_evidence_is_sent_and_cited(sdk):
    requests, clients = sdk(output())
    result = module.run_openai_rag(QUESTION, top_k=1)
    assert result.status == "answered" and result.generator == "openai" and len(requests) == 1
    request = requests[0]
    data = json.loads(request["input"])
    assert data["question"] == QUESTION and data["evidence"] == app.evidence_payload(result.retrieved)
    assert [item["chunk_id"] for item in data["evidence"]] == ["refunds-current:p1"]
    assert "30 days" not in request["input"] and "archived" not in request["input"]
    assert request["model"] == "gpt-6-astra" and request["reasoning"] == {"effort": "low"}
    assert request["store"] is False and request["text"]["format"]["strict"] is True
    assert clients[0]["closed"] and clients[0]["options"]["max_retries"] == 0 and clients[0]["options"]["timeout"] == 30


def test_no_evidence_needs_neither_sdk_nor_key(monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)
    result = module.run_openai_rag("How do I reset my password?")
    assert result.status == "insufficient_evidence" and result.generator == "none"


def test_empty_or_budget_excluded_evidence_does_not_call_api(sdk):
    requests, clients = sdk()
    result = module.run_openai_rag(QUESTION, app.KnowledgeBase(()))
    assert result.status == "insufficient_evidence"
    large = app.KnowledgeBase((app.Document("large", "Large", 1, "current", "refund request " * 35),))
    assert module.run_openai_rag("refund request", large, max_context_chars=200).status == "insufficient_evidence"
    assert not requests and not clients


def test_missing_key_for_relevant_evidence_is_clear_error(sdk, monkeypatch):
    requests, clients = sdk()
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(ValueError, match="Missing OPENAI_API_KEY"):
        module.run_openai_rag(QUESTION)
    assert not requests and not clients


@pytest.mark.parametrize("raw", ["not JSON", "[]", "{}", output("refunds-archived:p1"),
    output("upload-errors:p1"), output(quote="Refund requests always receive automatic approval."),
    '{"status":"answered","answer":"Unsupported","citations":[]}',
    '{"status":"insufficient_evidence","answer":"Unsupported","citations":[]}',
    '{"status":"unknown","answer":"Text","citations":[]}'])
def test_invalid_or_fabricated_citations_do_not_produce_answer(sdk, raw):
    requests, clients = sdk(raw)
    with pytest.raises(ValueError):
        module.run_openai_rag(QUESTION, top_k=1)
    assert len(requests) == 1 and clients[0]["closed"]


@pytest.mark.parametrize("status,raw", [("failed", ""), ("incomplete", "partial"),
    ("completed", ""), ("completed", " "), ("completed", None)])
def test_incomplete_or_refused_generation_is_not_an_answer(sdk, status, raw):
    requests, clients = sdk(raw, status=status)
    with pytest.raises(RuntimeError):
        module.run_openai_rag(QUESTION)
    assert len(requests) == 1 and clients[0]["closed"]


def test_model_can_decline_even_when_retrieval_returns_passages(sdk):
    requests, _ = sdk(json.dumps({"status": "insufficient_evidence", "answer": "", "citations": []}))
    result = module.run_openai_rag(QUESTION)
    assert result.status == "insufficient_evidence" and result.answer == app.ABSTENTION
    assert result.retrieved and not result.citations and len(requests) == 1


def test_api_failure_closes_client_without_retry(sdk):
    requests, clients = sdk(error=RuntimeError("service unavailable"))
    with pytest.raises(RuntimeError, match="unavailable"):
        module.run_openai_rag(QUESTION)
    assert len(requests) == 1 and clients[0]["closed"]


@pytest.mark.parametrize("query,options", [("", {}), (None, {}), (QUESTION, {"top_k": True}),
    (QUESTION, {"max_context_chars": 0}), (QUESTION, {"min_score": float("nan")})])
def test_bad_input_before_any_billable_request(sdk, query, options):
    requests, clients = sdk()
    with pytest.raises(ValueError):
        module.run_openai_rag(query, **options)
    assert not requests and not clients


@pytest.mark.parametrize("explicit,expected", [(None, "gpt-6.1-sol"), ("gpt-6-astra", "gpt-6-astra")])
def test_model_override_precedence(sdk, monkeypatch, explicit, expected):
    requests, _ = sdk(output())
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6.1-sol")
    module.run_openai_rag(QUESTION, model=explicit)
    assert requests[0]["model"] == expected
