"""Current-source filtering, multiple documents, and insufficient evidence."""
from pathlib import Path
import sys

if __package__:
    from ..app import KnowledgeBase, load_documents, print_run, run_rag
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import KnowledgeBase, load_documents, print_run, run_rag


if __name__ == "__main__":
    documents = load_documents()
    kb = KnowledgeBase(documents)
    print("Excluded archived documents:", [d.doc_id for d in documents if d.state == "archived"])
    for question, top_k in (("What invoice reference and charge dates are needed for duplicate charges and refund requests?", 2),
                            ("Does cancellation automatically refund earlier charges?", 1),
                            ("How do I reset my password?", 3)):
        print()
        print_run(run_rag(question, kb, top_k=top_k))
