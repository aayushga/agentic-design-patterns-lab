"""Approval is bound to the exact revision; terminal states never dispatch."""
from dataclasses import FrozenInstanceError
import importlib

import pytest

app = importlib.import_module("patterns.13-human-in-the-loop.app")


def submit(queue, **kwargs):
    return queue.submit(app.DEMO_QUERY, app.local_draft(app.DEMO_QUERY), **kwargs)


def test_pending_has_no_authority_until_explicit_approval():
    queue = app.ReviewQueue()
    review = submit(queue)
    assert review.state == "pending" and review.approved_revision is None and not queue.outbox
    with pytest.raises(ValueError, match="pending"):
        queue.dispatch(review.review_id, 1)
    approved = queue.approve(review.review_id, 1, reviewer="Alice")
    assert approved.approved_revision == approved.revision == 1
    delivery = queue.dispatch(review.review_id, 1)
    assert delivery.text == approved.draft and delivery.reviewer == "Alice" and delivery.simulated
    assert queue.get(review.review_id).state == "dispatched" and queue.outbox == (delivery,)
    assert [e.action for e in queue.get(review.review_id).history] == ["submitted", "approved", "dispatched"]


def test_edit_clears_prior_approval_and_requires_review_of_exact_new_text():
    queue = app.ReviewQueue()
    original = submit(queue)
    approved = queue.approve(original.review_id, 1, reviewer="Alice")
    edited = queue.edit(original.review_id, 1, "Please share the invoice reference for review.", reviewer="Bob")
    assert edited.revision == 2 and edited.state == "pending" and edited.approved_revision is None and edited.reviewer is None
    assert edited.expires_at == original.expires_at  # Editing cannot extend a deadline.
    assert approved.draft == original.draft and approved.state == "approved"
    with pytest.raises(ValueError, match="Stale"):
        queue.dispatch(original.review_id, 1)
    with pytest.raises(ValueError, match="pending"):
        queue.dispatch(original.review_id, 2)
    with pytest.raises(ValueError, match="Stale"):
        queue.approve(original.review_id, 1, reviewer="Alice")
    queue.approve(original.review_id, 2, reviewer="Bob")
    assert queue.dispatch(original.review_id, 2).text == edited.draft


@pytest.mark.parametrize("approved_first", [False, True])
def test_rejection_is_terminal_and_can_revoke_approval(approved_first):
    queue = app.ReviewQueue()
    review = submit(queue)
    if approved_first:
        queue.approve(review.review_id, 1, reviewer="Alice")
    rejected = queue.reject(review.review_id, 1, reviewer="Bob", reason="Need more context.")
    assert rejected.state == "rejected" and rejected.approved_revision is None
    for action in (lambda: queue.dispatch(review.review_id, 1),
                   lambda: queue.approve(review.review_id, 1, reviewer="Alice"),
                   lambda: queue.edit(review.review_id, 1, "New text", reviewer="Alice")):
        with pytest.raises(ValueError, match="rejected"):
            action()
    assert not queue.outbox and rejected.history[-1].note == "Need more context."


@pytest.mark.parametrize("approved_first", [False, True])
def test_deadline_expires_pending_or_approved_review_exactly_at_boundary(approved_first):
    now = [10.0]
    queue = app.ReviewQueue(clock=lambda: now[0])
    review = submit(queue, ttl_seconds=5)
    if approved_first:
        queue.approve(review.review_id, 1, reviewer="Alice")
    now[0] = 14.9
    assert queue.get(review.review_id).state != "expired"
    now[0] = 15
    expired = queue.get(review.review_id)
    assert expired.state == "expired" and expired.approved_revision is None and expired.reviewer is None
    with pytest.raises(ValueError, match="expired"):
        queue.dispatch(review.review_id, 1)
    with pytest.raises(ValueError, match="expired"):
        queue.approve(review.review_id, 1, reviewer="Alice")
    assert not queue.outbox
    assert sum(e.action == "expired" for e in queue.get(review.review_id).history) == 1


def test_duplicate_dispatch_and_post_dispatch_edits_are_blocked():
    queue = app.ReviewQueue()
    review = submit(queue)
    queue.approve(review.review_id, 1, reviewer="Alice")
    queue.dispatch(review.review_id, 1)
    for action in (lambda: queue.dispatch(review.review_id, 1),
                   lambda: queue.edit(review.review_id, 1, "Changed", reviewer="Bob"),
                   lambda: queue.reject(review.review_id, 1, reviewer="Bob", reason="Too late")):
        with pytest.raises(ValueError, match="dispatched"):
            action()
    assert len(queue.outbox) == 1


def test_returned_review_delivery_and_outbox_cannot_be_mutated():
    queue = app.ReviewQueue()
    review = submit(queue)
    with pytest.raises(FrozenInstanceError):
        review.state = "approved"
    with pytest.raises(FrozenInstanceError):
        review.history[0].action = "approved"
    queue.approve(review.review_id, 1, reviewer="Alice")
    delivery = queue.dispatch(review.review_id, 1)
    with pytest.raises(FrozenInstanceError):
        delivery.text = "Replaced after review"
    assert isinstance(queue.outbox, tuple)


def test_review_ids_and_approvals_are_isolated():
    queue = app.ReviewQueue()
    first, second = submit(queue), submit(queue)
    assert first.review_id != second.review_id
    queue.approve(first.review_id, 1, reviewer="Alice")
    with pytest.raises(ValueError, match="pending"):
        queue.dispatch(second.review_id, 1)
    with pytest.raises(ValueError, match="Unknown"):
        queue.approve("missing", 1, reviewer="Alice")
    assert not queue.outbox


def test_capacity_and_revision_budgets_do_not_modify_existing_state():
    queue = app.ReviewQueue(max_reviews=1, max_revisions=2)
    review = submit(queue)
    with pytest.raises(ValueError, match="capacity"):
        submit(queue)
    edited = queue.edit(review.review_id, 1, "Revision two", reviewer="Alice")
    with pytest.raises(ValueError, match="budget"):
        queue.edit(review.review_id, 2, "Revision three", reviewer="Alice")
    assert queue.get(review.review_id) == edited and not queue.outbox


@pytest.mark.parametrize("query,draft,ttl", [("", "draft", 300), (None, "draft", 300),
    ("q" * 1001, "draft", 300), ("query", "", 300), ("query", "d" * 1201, 300),
    ("query", "draft", 0), ("query", "draft", True), ("query", "draft", float("nan")),
    ("query", "draft", float("inf")), ("query", "draft", 3601)])
def test_invalid_submission_does_not_consume_capacity(query, draft, ttl):
    queue = app.ReviewQueue(max_reviews=1)
    with pytest.raises(ValueError):
        queue.submit(query, draft, ttl_seconds=ttl)
    assert submit(queue).state == "pending"


@pytest.mark.parametrize("revision", [True, 0, -1, 1.5, "1"])
def test_invalid_revision_cannot_approve(revision):
    queue = app.ReviewQueue()
    review = submit(queue)
    with pytest.raises(ValueError):
        queue.approve(review.review_id, revision, reviewer="Alice")
    assert queue.get(review.review_id) == review


def test_invalid_edit_and_empty_reviewer_leave_approval_unchanged():
    queue = app.ReviewQueue()
    review = submit(queue)
    approved = queue.approve(review.review_id, 1, reviewer="Alice")
    for draft, reviewer in [("", "Bob"), (review.draft, "Bob"), ("Changed", "")]:
        with pytest.raises(ValueError):
            queue.edit(review.review_id, 1, draft, reviewer=reviewer)
    assert queue.get(review.review_id) == approved


@pytest.mark.parametrize("commands,state,count", [(["approve"], "dispatched", 1),
    (["edit", "Human corrected draft", "approve"], "dispatched", 1),
    (["reject"], "rejected", 0), (["quit"], "pending", 0),
    (["not a decision", "quit"], "pending", 0)])
def test_actual_interactive_flow_commands(commands, state, count):
    queue = app.ReviewQueue()
    review = submit(queue)
    answers = iter(commands)
    result = app.review_interactively(queue, review.review_id, read=lambda _: next(answers))
    assert result.state == state and len(queue.outbox) == count
    if commands[0] == "edit":
        assert result.revision == 2 and queue.outbox[0].text == "Human corrected draft"


@pytest.mark.parametrize("failure", [EOFError, KeyboardInterrupt])
def test_interactive_interruption_never_means_approval(failure):
    queue = app.ReviewQueue()
    review = submit(queue)
    def interrupted(_):
        raise failure()
    assert app.review_interactively(queue, review.review_id, read=interrupted).state == "pending"
    assert not queue.outbox


def test_approval_entered_after_deadline_is_blocked():
    now = [0.0]
    queue = app.ReviewQueue(clock=lambda: now[0])
    review = submit(queue, ttl_seconds=1)
    def late_input(_):
        now[0] = 1
        return "approve"
    result = app.review_interactively(queue, review.review_id, read=late_input)
    assert result.state == "expired" and not queue.outbox
