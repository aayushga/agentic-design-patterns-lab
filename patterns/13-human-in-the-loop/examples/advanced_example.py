"""Editing clears approval; rejection, expiry, and duplicates remain blocked."""
from pathlib import Path
import sys

if __package__:
    from ..app import DEMO_QUERY, ReviewQueue, local_draft
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import DEMO_QUERY, ReviewQueue, local_draft


def blocked(label, action):
    try:
        action()
    except ValueError as exc:
        print(label + ":", exc)


if __name__ == "__main__":
    print("SCRIPTED REVIEWER DEMO: EDIT AND REVIEW AGAIN")
    queue = ReviewQueue()
    original = queue.submit(DEMO_QUERY, local_draft(DEMO_QUERY))
    queue.approve(original.review_id, 1, reviewer="Demo reviewer")
    edited = queue.edit(original.review_id, 1,
                        "Please share the invoice reference and charge dates so support can review the duplicate-charge report.",
                        reviewer="Demo reviewer")
    print(f"After edit: revision {edited.revision}, state {edited.state}, approval {edited.approved_revision}")
    blocked("Old approval blocked", lambda: queue.dispatch(original.review_id, 1))
    blocked("New draft still needs approval", lambda: queue.dispatch(edited.review_id, 2))
    queue.approve(edited.review_id, 2, reviewer="Demo reviewer")
    delivery = queue.dispatch(edited.review_id, 2)
    print("Dispatched approved revision:", delivery.revision)
    print("Approved text:", delivery.text)
    blocked("Duplicate blocked", lambda: queue.dispatch(edited.review_id, 2))

    print("\nREJECTION")
    rejected = queue.submit(DEMO_QUERY, local_draft(DEMO_QUERY))
    queue.reject(rejected.review_id, 1, reviewer="Demo reviewer", reason="Needs more investigation.")
    blocked("Rejected draft blocked", lambda: queue.dispatch(rejected.review_id, 1))

    print("\nEXPIRY (SIMULATED CLOCK)")
    now = [0.0]
    expiring = ReviewQueue(clock=lambda: now[0])
    late = expiring.submit(DEMO_QUERY, local_draft(DEMO_QUERY), ttl_seconds=5)
    expiring.approve(late.review_id, 1, reviewer="Demo reviewer")
    now[0] = 5
    blocked("Expired approval blocked", lambda: expiring.dispatch(late.review_id, 1))
    print("Simulated outbox entries:", len(queue.outbox), "| expired queue:", len(expiring.outbox))
    print("No API calls or real messages; reviewer decisions above were scripted.")
