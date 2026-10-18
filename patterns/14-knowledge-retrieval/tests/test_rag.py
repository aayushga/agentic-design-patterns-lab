"""Retrieval relevance, bounded evidence, metadata filtering, and provenance."""
from dataclasses import FrozenInstanceError, asdict, replace
import importlib
import json

import pytest

app = importlib.import_module("patterns.14-knowledge-retrieval.app")
QUESTION = "Within how many days can I request a refund?"


@pytest.fixture
def kb():
    return app.KnowledgeBase(app.load_documents())


def answer_for(hit):
    return {"status": "answered", "answer": "The demo policy requires requests within 14 days.",
            "citations": [{"chunk_id": hit.chunk.chunk_id, "quote": hit.chunk.text}]}


def test_basic_answer_uses_current_source_and_exact_evidence(kb):
    result = app.run_rag(QUESTION, kb, top_k=1)
    assert result.status == "answered" and result.generator == "local_extractive"
    assert len(result.retrieved) == len(result.citations) == 1
    citation = result.citations[0]
    assert citation.chunk_id == "refunds-current:p1" and citation.revision == 2
    assert "14 days" in result.answer and "30 days" not in result.answer
    assert citation.quote == result.retrieved[0].chunk.text
    assert result.source == "fictional DemoDesk knowledge base"


def test_archived_content_never_enters_index_or_context(kb):
    assert not any("archived" in c.doc_id or "30 days" in c.text for c in kb.chunks)
    hits = kb.retrieve("refund requests within 30 days", top_k=5)
    assert hits and all("archived" not in h.chunk.doc_id for h in hits)
    assert "30 days" not in json.dumps(app.evidence_payload(hits))


def test_multi_document_question_retrieves_both_relevant_policies(kb):
    result = app.run_rag("What invoice reference and charge dates are needed for duplicate charges and refund requests?", kb, top_k=2)
    assert {h.chunk.doc_id for h in result.retrieved} == {"duplicate-charges", "refunds-current"}
    assert len(result.citations) == 2 and "not a verified billing error" in result.answer


def test_cancellation_does_not_become_a_refund_promise(kb):
    result = app.run_rag("Does cancellation automatically refund earlier charges?", kb, top_k=1)
    assert result.citations[0].chunk_id == "cancellation:p2"
    assert "does not automatically refund" in result.answer


@pytest.mark.parametrize("query", ["How do I reset my password?", "What is the weather forecast?", "the and of"])
def test_unanswered_questions_abstain_without_inventing_sources(kb, query):
    result = app.run_rag(query, kb)
    assert result.status == "insufficient_evidence" and result.answer == app.ABSTENTION
    assert not result.retrieved and not result.citations and result.generator == "none"


def test_retrieval_is_deterministic_with_stable_tie_breaking():
    docs = (app.Document("b", "B", 1, "current", "Refund requests require an invoice reference."),
            app.Document("a", "A", 1, "current", "Refund requests require an invoice reference."))
    first = app.KnowledgeBase(docs).retrieve("refund request", min_score=0.1)
    second = app.KnowledgeBase(tuple(reversed(docs))).retrieve("refund request", min_score=0.1)
    assert first == second and [h.chunk.chunk_id for h in first] == ["a:p1", "b:p1"]


def test_metadata_and_content_updates_change_answer_without_model_training():
    documents = app.load_documents()
    updated = tuple(replace(d, revision=3, body=d.body.replace("14 days", "7 days"))
                    if d.doc_id == "refunds-current" else d for d in documents)
    result = app.run_rag(QUESTION, app.KnowledgeBase(updated), top_k=1)
    assert "7 days" in result.answer and "14 days" not in result.answer
    assert result.citations[0].revision == 3


def test_context_budget_keeps_whole_chunks_and_counts_serialized_metadata(kb):
    hits = kb.retrieve("refund invoice charge date request", top_k=5, max_context_chars=500)
    assert hits and len(json.dumps(app.evidence_payload(hits), ensure_ascii=False)) <= 500
    assert all(h.chunk in kb.chunks for h in hits)
    large = app.KnowledgeBase((app.Document("large", "Large", 1, "current", "refund request " * 35),))
    assert not large.retrieve("refund request", max_context_chars=200)


def test_score_threshold_can_force_abstention_and_empty_index_is_safe(kb):
    assert app.run_rag(QUESTION, kb, min_score=10000).status == "insufficient_evidence"
    assert app.run_rag(QUESTION, app.KnowledgeBase(())).status == "insufficient_evidence"


def test_paragraph_chunk_ids_and_whitespace_normalization():
    doc = app.Document("demo", "Demo", 1, "current", "First refund   paragraph.\n\nSecond invoice paragraph.")
    chunks = app.KnowledgeBase((doc,)).chunks
    assert [c.chunk_id for c in chunks] == ["demo:p1", "demo:p2"]
    assert chunks[0].text == "First refund paragraph."
    with pytest.raises(FrozenInstanceError):
        chunks[0].text = "Changed"


@pytest.mark.parametrize("options", [{"top_k": 0}, {"top_k": 6}, {"top_k": True},
    {"min_score": 0}, {"min_score": float("nan")}, {"min_score": float("inf")},
    {"max_context_chars": 199}, {"max_context_chars": 6001}, {"max_context_chars": True}])
def test_invalid_retrieval_limits(kb, options):
    with pytest.raises(ValueError):
        kb.retrieve(QUESTION, **options)


@pytest.mark.parametrize("query", ["", None, "q" * 1001])
def test_invalid_query(kb, query):
    with pytest.raises(ValueError):
        app.run_rag(query, kb)


def test_file_validation_and_bounded_read(tmp_path):
    path = tmp_path / "kb.json"
    for content in ("not JSON", "{}", '[{"doc_id":"missing-fields"}]', " " * 100001):
        path.write_text(content)
        with pytest.raises(ValueError):
            app.load_documents(path)
    path.write_text("[]")
    assert app.load_documents(path) == ()


def test_duplicate_ids_long_paragraphs_and_chunk_limits_are_rejected():
    doc = app.Document("demo", "Demo", 1, "current", "Refund request policy.")
    for docs in ((doc, doc), (replace(doc, body="r" * 601),),
                 (replace(doc, body="\n\n".join("Refund policy." for _ in range(101))),)):
        with pytest.raises(ValueError):
            app.KnowledgeBase(docs)


@pytest.mark.parametrize("fields", [{"doc_id": "../secret"}, {"revision": True},
    {"revision": 0}, {"state": "unknown"}, {"body": ""}, {"title": ""}])
def test_invalid_document_metadata(fields):
    with pytest.raises(ValueError):
        app.Document(**({"doc_id": "demo", "title": "Demo", "revision": 1,
                        "state": "current", "body": "Refund request policy."} | fields))


@pytest.mark.parametrize("kind", ["unknown", "archived", "unsupplied", "fabricated_quote", "tiny_quote", "duplicate", "no_citations"])
def test_citations_must_belong_to_supplied_chunks_and_contain_real_excerpts(kb, kind):
    hits = kb.retrieve(QUESTION, top_k=1)
    value = answer_for(hits[0])
    citation = value["citations"][0]
    if kind in ("unknown", "archived", "unsupplied"):
        citation["chunk_id"] = {"unknown": "invented:p1", "archived": "refunds-archived:p1", "unsupplied": "upload-errors:p1"}[kind]
    elif kind == "fabricated_quote":
        citation["quote"] = "Refunds are guaranteed for all customers forever."
    elif kind == "tiny_quote":
        citation["quote"] = "a"
    elif kind == "duplicate":
        value["citations"].append(dict(citation))
    else:
        value["citations"] = []
    with pytest.raises(ValueError):
        app.validate_answer(QUESTION, value, hits, generator="test")


def test_citation_titles_and_revisions_come_from_host_metadata(kb):
    hits = kb.retrieve(QUESTION, top_k=1)
    result = app.validate_answer(QUESTION, answer_for(hits[0]), hits, generator="test")
    assert asdict(result.citations[0])["title"] == hits[0].chunk.title
    assert result.citations[0].revision == hits[0].chunk.revision


def test_valid_abstention_is_fixed_text_without_claims(kb):
    hits = kb.retrieve(QUESTION)
    value = {"status": "insufficient_evidence", "answer": "", "citations": []}
    result = app.validate_answer(QUESTION, value, hits, generator="test")
    assert result.answer == app.ABSTENTION and result.retrieved == hits and not result.citations
    value["answer"] = "Unsupported answer disguised as abstention"
    with pytest.raises(ValueError):
        app.validate_answer(QUESTION, value, hits, generator="test")
