"""Draft → pause for human review → dispatch only the approved revision.

Single-process, in-memory simulation. No real messages are ever sent.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import json
import math
import time
from uuid import uuid4


def validate_text(value: str, name: str, limit: int) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{name} must be non-empty text of at most {limit} characters")


def validate_ttl(seconds: float) -> None:
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 1 <= seconds <= 3600:
        raise ValueError("ttl_seconds must be a finite number between 1 and 3600")


@dataclass(frozen=True)
class AuditEvent:
    action: str
    revision: int
    actor: str
    note: str


@dataclass(frozen=True)
class Review:
    review_id: str
    query: str
    draft: str
    revision: int
    state: str
    approved_revision: int | None
    reviewer: str | None
    expires_at: float
    history: tuple[AuditEvent, ...]


@dataclass(frozen=True)
class SimulatedDelivery:
    review_id: str
    revision: int
    text: str
    reviewer: str
    simulated: bool = True


class ReviewQueue:
    """Trusted local reviewer controls a versioned approval gate.

    Reviewer labels are audit data, not authentication. Not thread-safe or durable.
    """
    def __init__(self, *, clock=time.monotonic, max_reviews: int = 20, max_revisions: int = 5):
        if type(max_reviews) is not int or not 1 <= max_reviews <= 100:
            raise ValueError("max_reviews must be an integer between 1 and 100")
        if type(max_revisions) is not int or not 1 <= max_revisions <= 10:
            raise ValueError("max_revisions must be an integer between 1 and 10")
        self._clock = clock
        self._max_reviews = max_reviews
        self._max_revisions = max_revisions
        self._reviews: dict[str, Review] = {}
        self._outbox: list[SimulatedDelivery] = []

    @property
    def outbox(self) -> tuple[SimulatedDelivery, ...]:
        return tuple(self._outbox)

    def check_submission(self, query: str, ttl_seconds: float) -> None:
        validate_text(query, "query", 1000)
        validate_ttl(ttl_seconds)
        if len(self._reviews) >= self._max_reviews:
            raise ValueError("Review queue capacity reached")

    def submit(self, query: str, draft: str, *, ttl_seconds: float = 300) -> Review:
        self.check_submission(query, ttl_seconds)
        validate_text(draft, "draft", 1200)
        review_id = "REV-" + uuid4().hex
        review = Review(review_id, query, draft, 1, "pending", None, None,
                        self._clock() + ttl_seconds,
                        (AuditEvent("submitted", 1, "assistant", "Human review required."),))
        self._reviews[review_id] = review
        return review

    def get(self, review_id: str) -> Review:
        validate_text(review_id, "review_id", 80)
        if review_id not in self._reviews:
            raise ValueError("Unknown review ID")
        review = self._reviews[review_id]
        if review.state in ("pending", "approved") and self._clock() >= review.expires_at:
            review = replace(review, state="expired", approved_revision=None, reviewer=None,
                             history=review.history + (AuditEvent("expired", review.revision, "system", "Review deadline reached."),))
            self._reviews[review_id] = review
        return review

    def _checked(self, review_id: str, revision: int, allowed: tuple[str, ...]) -> Review:
        if type(revision) is not int or revision < 1:
            raise ValueError("revision must be a positive integer")
        review = self.get(review_id)
        if revision != review.revision:
            raise ValueError("Stale revision; review the latest draft before acting")
        if review.state not in allowed:
            raise ValueError(f"Operation is not permitted while review is {review.state}")
        return review

    def edit(self, review_id: str, revision: int, draft: str, *, reviewer: str) -> Review:
        validate_text(draft, "draft", 1200)
        validate_text(reviewer, "reviewer", 80)
        review = self._checked(review_id, revision, ("pending", "approved"))
        if draft == review.draft:
            raise ValueError("Edited draft must differ from the previous revision")
        if review.revision >= self._max_revisions:
            raise ValueError("Revision budget reached; submit a new review")
        updated = replace(review, draft=draft, revision=revision + 1, state="pending",
                          approved_revision=None, reviewer=None,
                          history=review.history + (AuditEvent("edited", revision + 1, reviewer, "Earlier approval cleared; review required."),))
        self._reviews[review_id] = updated
        return updated

    def approve(self, review_id: str, revision: int, *, reviewer: str) -> Review:
        validate_text(reviewer, "reviewer", 80)
        review = self._checked(review_id, revision, ("pending",))
        updated = replace(review, state="approved", approved_revision=revision, reviewer=reviewer,
                          history=review.history + (AuditEvent("approved", revision, reviewer, "Approved this exact draft revision."),))
        self._reviews[review_id] = updated
        return updated

    def reject(self, review_id: str, revision: int, *, reviewer: str, reason: str) -> Review:
        validate_text(reviewer, "reviewer", 80)
        validate_text(reason, "reason", 300)
        review = self._checked(review_id, revision, ("pending", "approved"))
        updated = replace(review, state="rejected", approved_revision=None, reviewer=None,
                          history=review.history + (AuditEvent("rejected", revision, reviewer, reason),))
        self._reviews[review_id] = updated
        return updated

    def dispatch(self, review_id: str, revision: int) -> SimulatedDelivery:
        review = self._checked(review_id, revision, ("approved",))
        if review.approved_revision != revision or review.reviewer is None:
            raise ValueError("Current draft has no matching approval")
        delivery = SimulatedDelivery(review_id, revision, review.draft, review.reviewer)
        updated = replace(review, state="dispatched",
                          history=review.history + (AuditEvent("dispatched", revision, "simulator", "Added approved text to the in-memory outbox once."),))
        self._reviews[review_id] = updated
        self._outbox.append(delivery)
        return delivery


DEMO_QUERY = "I was charged twice for my subscription. Can you help?"


def local_draft(query: str) -> str:
    validate_text(query, "query", 1000)
    return ("Thanks for reporting the issue. Please share the relevant reference and "
            "details so support can review it. No account has been checked or changed.")


def print_review(review: Review) -> None:
    print(f"Review: {review.state} | revision {review.revision}")
    print("Customer query:", review.query)
    print("Draft for human review:", review.draft)


def review_interactively(queue: ReviewQueue, review_id: str, *, read=input) -> Review:
    """Only explicit terminal input can approve; EOF/quit never dispatches."""
    while True:
        review = queue.get(review_id)
        print_review(review)
        if review.state != "pending":
            return review
        try:
            command = read("Decision [approve/edit/reject/quit]: ").strip().lower()
            if command == "quit":
                print("Left pending; nothing was dispatched.")
                return queue.get(review_id)
            if command == "approve":
                queue.approve(review_id, review.revision, reviewer="Local reviewer")
                queue.dispatch(review_id, review.revision)
                print("Approved revision added to simulated outbox. No real message was sent.")
                return queue.get(review_id)
            if command == "edit":
                draft = read("Replacement draft: ")
                queue.edit(review_id, review.revision, draft, reviewer="Local reviewer")
            elif command == "reject":
                return queue.reject(review_id, review.revision, reviewer="Local reviewer", reason="Reviewer declined this draft.")
            else:
                print("Enter approve, edit, reject, or quit.")
        except (EOFError, KeyboardInterrupt):
            print("Review ended; no new dispatch was performed.")
            return queue.get(review_id)
        except ValueError as exc:
            print(exc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Review a free local support draft before simulated dispatch")
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()
    queue = ReviewQueue()
    review = queue.submit(DEMO_QUERY, local_draft(DEMO_QUERY))
    if args.interactive:
        review = review_interactively(queue, review.review_id)
    print(json.dumps(asdict(review), indent=2))
    print("Simulated outbox entries:", len(queue.outbox))
    print("In-memory demo only; no API call or real message. Use --interactive on startup to review before exiting.")


if __name__ == "__main__":
    main()
