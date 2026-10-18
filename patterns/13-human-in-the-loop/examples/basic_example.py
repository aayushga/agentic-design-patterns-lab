"""Scripted reviewer decisions demonstrate the gate; no real human is contacted."""
from pathlib import Path
import sys

if __package__:
    from ..app import DEMO_QUERY, ReviewQueue, local_draft, print_review
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import DEMO_QUERY, ReviewQueue, local_draft, print_review


if __name__ == "__main__":
    print("SCRIPTED REVIEWER DEMO")
    queue = ReviewQueue()
    review = queue.submit(DEMO_QUERY, local_draft(DEMO_QUERY))
    print_review(review)
    try:
        queue.dispatch(review.review_id, review.revision)
    except ValueError as exc:
        print("Dispatch blocked:", exc)
    approved = queue.approve(review.review_id, review.revision, reviewer="Demo reviewer")
    print(f"Scripted decision: approve revision {approved.revision}")
    delivery = queue.dispatch(approved.review_id, approved.revision)
    print("State:", queue.get(review.review_id).state)
    print("Simulated outbox entries:", len(queue.outbox))
    print("Approved text:", delivery.text)
    print("No API call or real message. Use app.py --interactive for actual terminal review.")
