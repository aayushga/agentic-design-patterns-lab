"""Bounded retries, safe fallbacks, and honest result provenance without I/O."""
import importlib

import pytest

app = importlib.import_module("patterns.12-exception-handling-and-recovery.app")


def operation(*outcomes):
    remaining = iter(outcomes)
    calls = []
    def call():
        calls.append(True)
        value = next(remaining)
        if isinstance(value, BaseException):
            raise value
        return value
    return call, calls


def test_immediate_success_needs_no_retry_wait_or_fallback():
    primary, calls = operation("valid")
    def forbidden(*args):
        pytest.fail("No wait or fallback should occur")
    result = app.recover(primary, str, fallback=forbidden, sleep=forbidden)
    assert result.status == "success" and result.value == "valid" and len(calls) == 1
    assert result.primary_attempts == 1 and len(result.events) == 1


def test_transient_retry_backoff_then_recovery_at_final_attempt():
    primary, calls = operation(app.TransientFailure("timeout"), app.TransientFailure("timeout"), "valid")
    waits = []
    result = app.recover(primary, str, sleep=waits.append, jitter=lambda: 1)
    assert result.status == "recovered" and result.primary_attempts == len(calls) == 3
    assert waits == [0.25, 0.5]
    assert [e.outcome for e in result.events] == ["transient", "retry_scheduled", "transient", "retry_scheduled", "success"]


def test_exhaustion_uses_one_validated_fallback():
    primary, calls = operation(*(app.TransientFailure("outage") for _ in range(3)))
    fallback, fallback_calls = operation("backup")
    waits, validations = [], []
    def validate(value):
        validations.append(value)
        return value.upper()
    result = app.recover(primary, validate, fallback=fallback, sleep=waits.append, jitter=lambda: 0)
    assert result.status == "degraded" and result.value == "BACKUP"
    assert len(calls) == 3 and len(fallback_calls) == 1 and validations == ["backup"]
    assert waits == [0.125, 0.25] and result.events[-1].stage == "fallback"


def test_invalid_primary_is_not_retried_and_fallback_is_validated():
    primary, calls = operation("bad")
    def validate(value):
        if value != "valid":
            raise app.InvalidOutput("invalid_output")
        return value
    result = app.recover(primary, validate, fallback=lambda: "valid")
    assert result.status == "degraded" and len(calls) == 1
    result = app.recover(lambda: "bad", validate, fallback=lambda: "also bad")
    assert result.status == "unavailable" and result.value is None
    assert result.events[-1].code == "invalid_output"


@pytest.mark.parametrize("failure", [app.TerminalFailure("not_found"), app.TerminalFailure("access_denied")])
def test_terminal_failures_never_retry_or_use_cache(failure):
    primary, calls = operation(failure)
    def forbidden():
        pytest.fail("Terminal failures must not fall back")
    result = app.recover(primary, str, fallback=forbidden)
    assert result.status == "unavailable" and len(calls) == 1 and result.value is None


@pytest.mark.parametrize("fallback_failure", [app.TransientFailure("outage"), app.TerminalFailure("cache_miss")])
def test_fallback_failure_is_not_retried(fallback_failure):
    primary, _ = operation(app.InvalidOutput("invalid_output"))
    fallback, calls = operation(fallback_failure)
    result = app.recover(primary, str, fallback=fallback)
    assert result.status == "unavailable" and len(calls) == 1 and result.events[-1].outcome == "failed"


@pytest.mark.parametrize("stage", ["primary", "validator", "fallback", "sleep"])
def test_unexpected_programming_errors_propagate(stage):
    def bug(*args):
        raise RuntimeError("unexpected implementation bug")
    primary = bug if stage == "primary" else (lambda: "valid")
    validator = bug if stage == "validator" else str
    kwargs = {}
    if stage in ("fallback", "sleep"):
        primary = lambda: (_ for _ in ()).throw(app.TransientFailure("outage"))
        kwargs = {"policy": app.RetryPolicy(max_attempts=1)} if stage == "fallback" else {}
    with pytest.raises(RuntimeError, match="implementation bug"):
        app.recover(primary, validator, fallback=bug if stage == "fallback" else None,
                    sleep=bug if stage == "sleep" else lambda _: None, **kwargs)


def test_keyboard_interrupt_is_not_swallowed():
    primary, _ = operation(KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        app.recover(primary, str)


def test_server_retry_after_is_respected_without_jitter():
    primary, _ = operation(app.TransientFailure("rate_limited", retry_after=1.5), "valid")
    waits = []
    result = app.recover(primary, str, sleep=waits.append, jitter=lambda: pytest.fail("No jitter for server delay"))
    assert result.status == "recovered" and waits == [1.5]


def test_long_server_delay_defers_primary_instead_of_retrying_early():
    primary, calls = operation(app.TransientFailure("rate_limited", retry_after=60))
    waits = []
    result = app.recover(primary, str, fallback=lambda: "backup", sleep=waits.append)
    assert result.status == "degraded" and len(calls) == 1 and not waits
    assert result.events[-2].outcome == "retry_deferred" and result.events[-2].delay_seconds == 60


def test_delay_cap_and_total_attempt_cap():
    primary, calls = operation(*(app.TransientFailure("outage") for _ in range(5)))
    waits = []
    result = app.recover(primary, str, policy=app.RetryPolicy(5, 1, 1.5), sleep=waits.append, jitter=lambda: 1)
    assert result.status == "unavailable" and len(calls) == 5
    assert waits == [1, 1.5, 1.5, 1.5]


@pytest.mark.parametrize("fields", [{"max_attempts": 0}, {"max_attempts": 6}, {"max_attempts": True},
    {"base_delay": -1}, {"base_delay": True}, {"base_delay": 3},
    {"max_delay": 31}, {"max_delay": float("nan")}, {"base_delay": float("inf")}])
def test_invalid_retry_policy(fields):
    with pytest.raises(ValueError):
        app.RetryPolicy(**fields)


@pytest.mark.parametrize("value", [-1, 2, True, float("nan"), "random"])
def test_invalid_jitter(value):
    primary, _ = operation(app.TransientFailure("timeout"))
    with pytest.raises(ValueError, match="jitter"):
        app.recover(primary, str, jitter=lambda: value)


def test_local_basic_and_degraded_cache_have_different_provenance():
    options = {"sleep": lambda _: None, "jitter": lambda: 1}
    primary = app.run_support(scenario="transient", **options)
    cached = app.run_support(scenario="outage", **options)
    assert primary.lookup.status == "recovered" and primary.lookup.value.status == "open"
    assert cached.lookup.status == "degraded" and cached.lookup.value.status == "waiting_for_details"
    assert "Older cached" in cached.message and "current status is unverified" in cached.message
    assert "Older cached" not in primary.message and "No real account" in primary.message


@pytest.mark.parametrize("scenario,cache,status,attempts", [
    ("healthy", True, "success", 1), ("malformed", True, "degraded", 1),
    ("not_found", True, "unavailable", 1), ("denied", True, "unavailable", 1),
    ("outage", False, "unavailable", 3)])
def test_local_recovery_scenarios(scenario, cache, status, attempts):
    result = app.run_support(scenario=scenario, use_cache=cache, sleep=lambda _: None)
    assert result.lookup.status == status and result.lookup.primary_attempts == attempts
    if status == "unavailable":
        assert result.lookup.value is None and "no status is confirmed" in result.message


@pytest.mark.parametrize("value", [None, [], {}, {"ticket_id": "T-101", "category": "billing", "status": "resolved", "summary": "A"},
    {"ticket_id": "T-999", "category": "billing", "status": "open", "summary": "A"},
    {"ticket_id": "T-101", "category": "billing", "status": "open", "summary": ""}])
def test_invalid_records_never_become_success(value):
    with pytest.raises(app.InvalidOutput):
        app.validate_record(value, "T-101")


@pytest.mark.parametrize("ticket_id", [None, "", "101", "T-101/../../secret"])
def test_invalid_ticket_id_rejected_before_service(ticket_id, monkeypatch):
    monkeypatch.setattr(app, "DemoService", lambda *args: pytest.fail("No service for bad input"))
    with pytest.raises(ValueError):
        app.run_support(ticket_id)


def test_no_record_leaks_between_runs():
    record = app.cached_record("T-101")
    record["status"] = "resolved"
    assert app.cached_record("T-101")["status"] == "waiting_for_details"
    assert app.lookup_ticket("T-999").status == "unavailable"
