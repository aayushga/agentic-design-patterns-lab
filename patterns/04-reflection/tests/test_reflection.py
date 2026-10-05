"""Offline tests for feedback, reviewed results, and bounded termination."""
import importlib

import pytest

app = importlib.import_module("patterns.04-reflection.app")


def test_default_reply_is_revised_and_rechecked():
    query = "I was charged twice."
    result = app.run_reflection(query)
    assert result.original_query == query
    assert result.initial_draft == "We received your request."
    assert result.approved and result.revisions == 1
    assert result.stop_reason == "approved"
    assert len(result.history[0].critique.issues) == 3
    assert result.history[-1].draft == result.final_draft
    assert result.history[-1].critique == app.Critique(True, [])
    assert query in result.final_draft


def test_feedback_and_draft_are_passed_to_reviser():
    calls = []
    feedback = app.Critique(False, ["add a next step"])

    def review(query, draft):
        calls.append(("review", query, draft))
        return feedback if draft == "first" else app.Critique(True, [])

    def revise(query, draft, critique):
        calls.append(("revise", query, draft, critique))
        return "second"

    result = app.run_reflection("ticket", producer=lambda _: "first",
                                reviewer=review, reviser=revise)
    assert calls == [("review", "ticket", "first"),
                     ("revise", "ticket", "first", feedback),
                     ("review", "ticket", "second")]
    assert result.final_draft == "second" and result.approved


def test_initial_approval_skips_generation_and_revision():
    def forbidden(*args):
        pytest.fail("An approved supplied draft should need only review")

    result = app.run_reflection("ticket", initial_draft="ready", producer=forbidden,
                                reviewer=lambda *_: app.Critique(True, []),
                                reviser=forbidden)
    assert result.revisions == 0 and result.stop_reason == "approved"


@pytest.mark.parametrize("budget", [0, 1, 2, 5])
def test_revision_budget_still_reviews_last_draft(budget):
    drafts = iter([f"draft {n}" for n in range(6)])
    result = app.run_reflection("ticket", producer=lambda _: next(drafts),
                                reviewer=lambda *_: app.Critique(False, ["needs work"]),
                                reviser=lambda *_: next(drafts), max_revisions=budget)
    assert not result.approved and result.stop_reason == "revision_limit"
    assert result.revisions == budget
    assert [step.revision for step in result.history] == list(range(budget + 1))
    assert result.final_draft == result.history[-1].draft == f"draft {budget}"


@pytest.mark.parametrize("candidate", ["first", " first   "])
def test_unchanged_draft_stops_without_claiming_approval(candidate):
    result = app.run_reflection("ticket", initial_draft="first",
                                reviewer=lambda *_: app.Critique(False, ["fix it"]),
                                reviser=lambda *_: candidate)
    assert result.stop_reason == "no_progress" and not result.approved
    assert result.final_draft == "first" and result.revisions == 0


def test_oscillating_drafts_stop_at_last_reviewed_candidate():
    drafts = iter(["second", "first"])
    result = app.run_reflection("ticket", initial_draft="first",
                                reviewer=lambda *_: app.Critique(False, ["fix it"]),
                                reviser=lambda *_: next(drafts))
    assert result.stop_reason == "no_progress"
    assert result.final_draft == "second" and result.revisions == 1
    assert [step.draft for step in result.history] == ["first", "second"]


@pytest.mark.parametrize("budget", [-1, 6, True, 1.5, "2"])
def test_invalid_budget_rejected_before_producer(budget):
    with pytest.raises(ValueError, match="max_revisions"):
        app.run_reflection("ticket", max_revisions=budget,
                           producer=lambda _: pytest.fail("must validate first"))


@pytest.mark.parametrize("query", ["", "  ", None])
def test_invalid_query(query):
    with pytest.raises(ValueError, match="non-empty query"):
        app.run_reflection(query)


@pytest.mark.parametrize("draft", ["", " ", 42])
def test_invalid_supplied_draft(draft):
    with pytest.raises(ValueError, match="initial_draft"):
        app.run_reflection("ticket", initial_draft=draft)


@pytest.mark.parametrize("feedback", [
    None, app.Critique("true", []), app.Critique(True, ["unresolved"]),
    app.Critique(False, []), app.Critique(False, "issue"),
    app.Critique(False, [""]), app.Critique(False, [42]),
])
def test_malformed_feedback_never_approves(feedback):
    with pytest.raises(ValueError, match="Critic"):
        app.run_reflection("ticket", reviewer=lambda *_: feedback)


@pytest.mark.parametrize("text", ["", " ", None])
@pytest.mark.parametrize("stage", ["producer", "reviser"])
def test_empty_stage_outputs_fail(text, stage):
    kwargs = {stage: lambda *_: text}
    with pytest.raises(ValueError, match="no usable text"):
        app.run_reflection("ticket", **kwargs)


def test_critic_exception_propagates():
    def broken(*args):
        raise RuntimeError("critic unavailable")

    with pytest.raises(RuntimeError, match="critic unavailable"):
        app.run_reflection("ticket", reviewer=broken)


def test_unsupported_claim_is_removed_and_rechecked():
    result = app.run_reflection("My payment failed.", initial_draft="Your refund is approved.")
    assert result.approved
    assert "approved" not in result.final_draft
    assert any(issue.startswith("promises:") for issue in result.history[0].critique.issues)


def test_quoted_customer_report_is_not_a_promise():
    result = app.run_reflection("The issue was never resolved.")
    assert result.approved and result.revisions == 1


def test_unfixable_length_remains_unapproved():
    result = app.run_reflection(" ".join(["problem"] * 85), max_revisions=3)
    assert not result.approved and result.stop_reason == "no_progress"
    assert any(issue.startswith("length:") for issue in result.history[-1].critique.issues)
