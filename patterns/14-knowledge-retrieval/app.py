"""Free lexical retrieval and extractive answers with paragraph citations.

The optional model synthesizes the same bounded context; no embeddings required.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import re

DEFAULT_KB = Path(__file__).resolve().parent / "knowledge_base" / "support_policies.json"
ABSTENTION = "I could not find enough supporting evidence in the fictional DemoDesk knowledge base to answer this question."
STOP_WORDS = set("a an and are as at be by can do does for from have how i in is it many me my of on or our please the this to we what when which who within with you your".split())


def validate_text(value: str, name: str, limit: int) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{name} must be non-empty text of at most {limit} characters")


def terms(text: str) -> tuple[str, ...]:
    """English word tokens and a small plural rule; this is not semantic search."""
    result = []
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if word in STOP_WORDS:
            continue
        if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        if word not in STOP_WORDS:
            result.append(word)
    return tuple(result)


@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    revision: int
    state: str
    body: str

    def __post_init__(self):
        if not isinstance(self.doc_id, str) or not re.fullmatch(r"[a-z0-9-]{1,60}", self.doc_id):
            raise ValueError("doc_id must be a short lowercase identifier")
        validate_text(self.title, "title", 120)
        validate_text(self.body, "body", 6000)
        if type(self.revision) is not int or not 1 <= self.revision <= 100:
            raise ValueError("revision must be an integer between 1 and 100")
        if self.state not in ("current", "archived"):
            raise ValueError("state must be current or archived")


def load_documents(path=DEFAULT_KB) -> tuple[Document, ...]:
    with Path(path).open("rb") as stream:
        raw = stream.read(100_001)
    if len(raw) > 100_000:
        raise ValueError("Knowledge base file exceeds the 100 KB demo limit")
    data = json.loads(raw)
    if not isinstance(data, list) or len(data) > 20:
        raise ValueError("Knowledge base must be a list of at most 20 documents")
    fields = {"doc_id", "title", "revision", "state", "body"}
    if any(not isinstance(item, dict) or set(item) != fields for item in data):
        raise ValueError("Invalid document object")
    return tuple(Document(**item) for item in data)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    revision: int
    text: str


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


def evidence_payload(hits: tuple[Hit, ...]) -> list[dict]:
    return [asdict(hit.chunk) for hit in hits]


class KnowledgeBase:
    """Small in-memory BM25 index over current document paragraphs only."""
    def __init__(self, documents: tuple[Document, ...]):
        if not isinstance(documents, tuple) or len(documents) > 20 or any(not isinstance(d, Document) for d in documents):
            raise ValueError("documents must be a tuple of at most 20 Document objects")
        if len({d.doc_id for d in documents}) != len(documents):
            raise ValueError("Document IDs must be unique")
        chunks = []
        for doc in documents:
            if doc.state != "current":
                continue
            for number, paragraph in enumerate(re.split(r"\n\s*\n", doc.body.strip()), 1):
                text = " ".join(paragraph.split())
                if not text or len(text) > 600:
                    raise ValueError("Each knowledge paragraph must contain 1 to 600 characters")
                chunks.append(Chunk(f"{doc.doc_id}:p{number}", doc.doc_id, doc.title, doc.revision, text))
        if len(chunks) > 100:
            raise ValueError("Knowledge base exceeds the 100-chunk demo limit")
        self.chunks = tuple(chunks)
        self._counts = tuple(Counter(terms(c.text)) for c in chunks)
        self._frequency = Counter(term for counts in self._counts for term in counts)
        self._average_length = sum(sum(c.values()) for c in self._counts) / len(chunks) if chunks else 1
        self._average_length = max(self._average_length, 1)

    def retrieve(self, query: str, *, top_k: int = 3, min_score: float = 0.5,
                 max_context_chars: int = 2500) -> tuple[Hit, ...]:
        validate_text(query, "query", 1000)
        if type(top_k) is not int or not 1 <= top_k <= 5:
            raise ValueError("top_k must be an integer between 1 and 5")
        if type(min_score) not in (int, float) or not math.isfinite(min_score) or min_score <= 0:
            raise ValueError("min_score must be a finite positive number")
        if type(max_context_chars) is not int or not 200 <= max_context_chars <= 6000:
            raise ValueError("max_context_chars must be an integer between 200 and 6000")
        query_terms = set(terms(query))
        if not query_terms:
            return ()
        ranked = []
        for chunk, counts in zip(self.chunks, self._counts):
            matched = query_terms.intersection(counts)
            if len(matched) < min(2, len(query_terms)):
                continue
            score = 0.0
            length = sum(counts.values())
            for term in sorted(matched):
                df = self._frequency[term]
                idf = math.log1p((len(self.chunks) - df + 0.5) / (df + 0.5))
                tf = counts[term]
                score += idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * length / self._average_length))
            if score >= min_score:
                ranked.append(Hit(chunk, round(score, 6)))
        ranked.sort(key=lambda h: (-h.score, h.chunk.chunk_id))
        selected = []
        for hit in ranked:
            candidate = tuple(selected + [hit])
            size = len(json.dumps(evidence_payload(candidate), ensure_ascii=False))
            if size <= max_context_chars:
                selected.append(hit)
            if len(selected) == top_k:
                break
        return tuple(selected)


@dataclass(frozen=True)
class Citation:
    chunk_id: str
    title: str
    revision: int
    quote: str


@dataclass(frozen=True)
class RAGResult:
    original_query: str
    status: str
    answer: str
    citations: tuple[Citation, ...]
    retrieved: tuple[Hit, ...]
    generator: str
    source: str = "fictional DemoDesk knowledge base"


def insufficient(query: str, hits: tuple[Hit, ...] = (), *, generator: str = "none") -> RAGResult:
    return RAGResult(query, "insufficient_evidence", ABSTENTION, (), hits, generator)


def validate_answer(query: str, value: object, hits: tuple[Hit, ...], *, generator: str) -> RAGResult:
    """Check citation provenance and exact excerpts, not semantic entailment."""
    if not isinstance(value, dict) or set(value) != {"status", "answer", "citations"}:
        raise ValueError("Invalid answer object")
    if value["status"] == "insufficient_evidence":
        if value["answer"] != "" or value["citations"] != []:
            raise ValueError("Abstention must have an empty answer and citations")
        return insufficient(query, hits, generator=generator)
    if value["status"] != "answered":
        raise ValueError("Invalid answer status")
    validate_text(value["answer"], "answer", 3500)
    if not isinstance(value["citations"], list) or not 1 <= len(value["citations"]) <= 5:
        raise ValueError("An answer must cite 1 to 5 supplied excerpts")
    known = {hit.chunk.chunk_id: hit.chunk for hit in hits}
    citations, seen = [], set()
    for item in value["citations"]:
        if not isinstance(item, dict) or set(item) != {"chunk_id", "quote"}:
            raise ValueError("Invalid citation object")
        if not isinstance(item["chunk_id"], str) or item["chunk_id"] not in known:
            raise ValueError("Citation must reference a supplied current chunk")
        chunk = known[item["chunk_id"]]
        validate_text(item["quote"], "quote", 600)
        key = (item["chunk_id"], item["quote"])
        if item["quote"] not in chunk.text or len(item["quote"]) < min(20, len(chunk.text)) or key in seen:
            raise ValueError("Citation must contain a distinct exact excerpt from its chunk")
        seen.add(key)
        citations.append(Citation(chunk.chunk_id, chunk.title, chunk.revision, item["quote"]))
    return RAGResult(query, "answered", value["answer"], tuple(citations), hits, generator)


def run_rag(query: str, knowledge_base: KnowledgeBase | None = None, **options) -> RAGResult:
    kb = knowledge_base if knowledge_base is not None else KnowledgeBase(load_documents())
    if not isinstance(kb, KnowledgeBase):
        raise ValueError("knowledge_base must be a KnowledgeBase")
    hits = kb.retrieve(query, **options)
    if not hits:
        return insufficient(query)
    # A deterministic extractive stand-in for generation: every sentence is an
    # actual retrieved paragraph. The optional model synthesizes this context.
    value = {"status": "answered", "answer": "Relevant excerpts from the fictional policies:\n" +
             "\n".join(f"- {hit.chunk.text}" for hit in hits),
             "citations": [{"chunk_id": h.chunk.chunk_id, "quote": h.chunk.text} for h in hits]}
    return validate_answer(query, value, hits, generator="local_extractive")


def print_run(result: RAGResult) -> None:
    print("Question:", result.original_query)
    print("Retrieved:", [f"{h.chunk.chunk_id} ({h.score:.3f})" for h in result.retrieved])
    print("Status:", result.status)
    print(result.answer)
    for citation in result.citations:
        print(f"Source [{citation.chunk_id}] revision {citation.revision}: {citation.title}")
    print("Fictional policies only; no real account lookup or action.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieve and cite fictional support-policy paragraphs")
    parser.add_argument("--query", default="Within how many days can I request a refund?")
    args = parser.parse_args()
    print(json.dumps(asdict(run_rag(args.query)), indent=2))
