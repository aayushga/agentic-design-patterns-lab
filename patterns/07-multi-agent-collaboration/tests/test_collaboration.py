"""Offline checks for role selection, message passing, and visible failures."""
from copy import deepcopy
import importlib

import pytest

app = importlib.import_module("patterns.07-multi-agent-collaboration.app")
QUERY = "I was charged twice. The app crashes during upload."


@pytest.mark.parametrize("query,roles", [("I was charged twice.", ["billing"]),
    ("The app crashes.", ["technical"]), (QUERY, ["billing", "technical"])])
def test_supervisor_assigns_relevant_roles(query, roles):
    result = app.run_collaboration(query)
    assert result.assignment.roles == roles and result.status == "completed"
    assert [item.sender for item in result.handoffs] == roles
    assert all(item.recipient == "writer" and item.status == "success" for item in result.handoffs)
    assert "No account changes" in result.final_response


def test_writer_receives_each_specialist_output_and_origin():
    received = []
    def writer(query, handoffs):
        received.extend(deepcopy(handoffs))
        assert query == QUERY
        return "Combined reply"
    result = app.run_collaboration(QUERY, writer=writer)
    assert received == result.handoffs and len(received) == 2
    assert received[0].findings[0].evidence == "I was charged twice."
    assert received[1].findings[0].evidence == "The app crashes during upload."
    assert "invoice" in received[0].findings[0].next_step
    assert "app version" in received[1].findings[0].next_step
    assert result.final_response == "Combined reply"


def test_only_selected_specialist_runs():
    def forbidden(*args):
        pytest.fail("Technical work was not assigned")
    result = app.run_collaboration("I was charged twice.",
        specialists={"billing": app.billing_specialist, "technical": forbidden})
    assert result.status == "completed" and len(result.handoffs) == 1


def test_empty_assignment_requests_clarification_without_agent_calls():
    def forbidden(*args):
        pytest.fail("No work assigned")
    result = app.run_collaboration("Hello", specialists={"billing": forbidden}, writer=forbidden)
    assert result.status == "needs_clarification" and not result.handoffs
    assert "describe" in result.final_response


def test_partial_specialist_failure_keeps_successful_work_and_marks_review():
    def broken(query):
        raise RuntimeError("sensitive-error-details")
    result = app.run_collaboration(QUERY,
        specialists={"billing": app.billing_specialist, "technical": broken})
    assert result.status == "needs_review" and result.handoffs[0].status == "success"
    assert result.handoffs[1].status == "error" and not result.handoffs[1].findings
    assert "human review" in result.final_response and "invoice" in result.final_response
    assert "sensitive-error-details" not in str(result)


def test_missing_specialist_is_explicit():
    result = app.run_collaboration(QUERY, specialists={"billing": app.billing_specialist})
    assert result.status == "needs_review" and result.handoffs[1].error == "Specialist is not configured"


def test_all_specialists_failed_skips_writer():
    result = app.run_collaboration(QUERY, specialists={},
        writer=lambda *_: pytest.fail("No usable findings"))
    assert result.status == "failed" and result.final_response is None
    assert all(item.status == "error" for item in result.handoffs)


@pytest.mark.parametrize("text", [None, "", " ", 42])
def test_unusable_writer_output_preserves_handoffs(text):
    result = app.run_collaboration(QUERY, writer=lambda *_: text)
    assert result.status == "failed" and result.final_response is None
    assert result.writer_error and len(result.handoffs) == 2
    assert all(item.status == "success" for item in result.handoffs)


def test_writer_exception_is_visible_without_leaking_error_details():
    def broken(*args):
        raise RuntimeError("sensitive-details")
    result = app.run_collaboration(QUERY, writer=broken)
    assert result.status == "failed" and result.writer_error
    assert "sensitive-details" not in str(result)


def test_writer_cannot_mutate_inspection_trace():
    def writer(query, handoffs):
        handoffs[0].findings[0].evidence = "tampered"
        handoffs.clear()
        return "Reply"
    result = app.run_collaboration(QUERY, writer=writer)
    assert result.handoffs[0].findings[0].evidence == "I was charged twice."
    assert len(result.handoffs) == 2


@pytest.mark.parametrize("assignment", [None, app.Assignment("billing", "reason"),
    app.Assignment(["billing", "billing"], "reason"), app.Assignment(["arbitrary"], "reason"),
    app.Assignment([42], "reason"), app.Assignment([[]], "reason"),
    app.Assignment(["billing"], ""), app.Assignment(["billing"], None)])
def test_invalid_assignment_rejected_before_specialist_execution(assignment):
    with pytest.raises(ValueError, match="Supervisor"):
        app.run_collaboration(QUERY, supervisor=lambda _: assignment,
            specialists={"billing": lambda *_: pytest.fail("must validate first")})


@pytest.mark.parametrize("findings", [None, [], ["not a finding"],
    [app.Finding("invented evidence", "assessment", "next")],
    [app.Finding("I was charged twice.", "", "next")],
    [app.Finding("I was charged twice.", "assessment", None)],
    [app.Finding("", "assessment", "next")],
    [app.Finding("I was charged twice.", "assessment", "next")] * 4])
def test_invalid_findings_do_not_reach_writer_as_success(findings):
    result = app.run_collaboration(QUERY, specialists={"billing": lambda _: findings,
                                                      "technical": app.technical_specialist})
    assert result.status == "needs_review"
    assert result.handoffs[0].status == "error" and not result.handoffs[0].findings
    assert "invented evidence" not in result.final_response


@pytest.mark.parametrize("specialists", [{"arbitrary": lambda _: []}, {"billing": None}, []])
def test_invalid_agent_registry_rejected(specialists):
    with pytest.raises(ValueError, match="Specialists"):
        app.run_collaboration(QUERY, specialists=specialists)


@pytest.mark.parametrize("query", [None, "", " "])
def test_blank_query_rejected_before_supervisor(query):
    with pytest.raises(ValueError, match="non-empty"):
        app.run_collaboration(query, supervisor=lambda _: pytest.fail("must validate first"))


def test_supervisor_failure_propagates():
    def broken(query):
        raise RuntimeError("supervisor unavailable")
    with pytest.raises(RuntimeError, match="supervisor unavailable"):
        app.run_collaboration(QUERY, supervisor=broken)
