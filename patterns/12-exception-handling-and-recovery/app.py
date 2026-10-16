"""Classify failures, retry safely, validate fallbacks, and report degradation.

Only read-only fictional data is used. Unexpected programming errors propagate.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import random
import re
import time
from typing import Callable


class RecoveryError(Exception):
    """Expected operational failure with a safe code, never a raw SDK message."""
    def __init__(self, code: str):
        if not isinstance(code, str) or not re.fullmatch(r"[a-z_]{1,40}", code):
            raise ValueError("Error code must be a short lowercase identifier")
        super().__init__(code)
        self.code = code


class TransientFailure(RecoveryError):
    def __init__(self, code: str, *, retry_after: float | None = None):
        super().__init__(code)
        if retry_after is not None and (type(retry_after) not in (int, float)
                or not math.isfinite(retry_after) or retry_after < 0):
            raise ValueError("retry_after must be a finite non-negative number")
        self.retry_after = retry_after


class TerminalFailure(RecoveryError):
    """No automatic retry or fallback: e.g. not found or permission denied."""


class InvalidOutput(RecoveryError):
    """Do not retry malformed output; a separately validated fallback is allowed."""


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 0.25
    max_delay: float = 2.0

    def __post_init__(self):
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 5:
            raise ValueError("max_attempts must be an integer between 1 and 5 (including the first attempt)")
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in (self.base_delay, self.max_delay)):
            raise ValueError("Retry delays must be finite numbers")
        if not 0 <= self.base_delay <= self.max_delay <= 30:
            raise ValueError("Retry delays must satisfy 0 <= base_delay <= max_delay <= 30")


@dataclass(frozen=True)
class Event:
    stage: str
    attempt: int
    outcome: str
    code: str | None = None
    delay_seconds: float | None = None


@dataclass(frozen=True)
class RecoveryResult:
    status: str
    value: object | None
    primary_attempts: int
    events: tuple[Event, ...]


def recover(operation: Callable, validate: Callable, *, policy: RetryPolicy = RetryPolicy(),
            fallback: Callable | None = None, sleep: Callable = time.sleep,
            jitter: Callable = random.random) -> RecoveryResult:
    """At most N primary attempts, followed by at most one fallback attempt.

    Only expected operational failures are caught. A long server-requested wait
    stops primary retries instead of retrying sooner than Retry-After permits.
    """
    if not isinstance(policy, RetryPolicy):
        raise ValueError("policy must be a RetryPolicy")
    events: list[Event] = []
    for attempt in range(1, policy.max_attempts + 1):
        try:
            value = validate(operation())
        except TerminalFailure as exc:
            events.append(Event("primary", attempt, "terminal", exc.code))
            return RecoveryResult("unavailable", None, attempt, tuple(events))
        except InvalidOutput as exc:
            events.append(Event("primary", attempt, "invalid", exc.code))
            break
        except TransientFailure as exc:
            events.append(Event("primary", attempt, "transient", exc.code))
            if attempt == policy.max_attempts:
                break
            if exc.retry_after is not None:
                delay = exc.retry_after
                if delay > policy.max_delay:
                    events.append(Event("primary", attempt, "retry_deferred", "server_wait_too_long", delay))
                    break
            else:
                fraction = jitter()
                if type(fraction) not in (int, float) or not math.isfinite(fraction) or not 0 <= fraction <= 1:
                    raise ValueError("jitter must return a number between 0 and 1")
                delay = min(policy.max_delay, policy.base_delay * 2 ** (attempt - 1)) * (0.5 + fraction / 2)
            events.append(Event("primary", attempt, "retry_scheduled", delay_seconds=delay))
            sleep(delay)
        else:
            events.append(Event("primary", attempt, "success"))
            return RecoveryResult("success" if attempt == 1 else "recovered", value, attempt, tuple(events))
    if fallback is not None:
        try:
            value = validate(fallback())
        except RecoveryError as exc:
            events.append(Event("fallback", 1, "failed", exc.code))
        else:
            events.append(Event("fallback", 1, "success"))
            return RecoveryResult("degraded", value, attempt, tuple(events))
    return RecoveryResult("unavailable", None, attempt, tuple(events))


def validate_ticket_id(ticket_id: str) -> None:
    if not isinstance(ticket_id, str) or not re.fullmatch(r"T-\d{3}", ticket_id):
        raise ValueError("ticket_id must have the form T-101")


@dataclass(frozen=True)
class TicketRecord:
    ticket_id: str
    category: str
    status: str
    summary: str


def validate_record(value: object, ticket_id: str) -> TicketRecord:
    if isinstance(value, TicketRecord):
        value = asdict(value)
    if not isinstance(value, dict) or set(value) != {"ticket_id", "category", "status", "summary"}:
        raise InvalidOutput("invalid_record")
    if (value["ticket_id"] != ticket_id or value["category"] not in ("billing", "technical")
            or value["status"] not in ("open", "waiting_for_details")
            or not isinstance(value["summary"], str) or not value["summary"].strip()
            or len(value["summary"]) > 300):
        raise InvalidOutput("invalid_record")
    return TicketRecord(**value)


SCENARIOS = ("healthy", "transient", "outage", "malformed", "not_found", "denied")


class DemoService:
    """Fault injection for read-only demo lookups, not an actual ticket service."""
    def __init__(self, scenario: str = "healthy"):
        if scenario not in SCENARIOS:
            raise ValueError(f"scenario must be one of {SCENARIOS}")
        self.scenario = scenario
        self.calls = 0

    def lookup(self, ticket_id: str) -> dict:
        self.calls += 1
        if self.scenario == "denied":
            raise TerminalFailure("access_denied")
        if ticket_id != "T-101" or self.scenario == "not_found":
            raise TerminalFailure("not_found")
        if self.scenario == "outage" or (self.scenario == "transient" and self.calls == 1):
            raise TransientFailure("service_unavailable")
        if self.scenario == "malformed":
            return {"ticket_id": ticket_id, "status": "unknown"}
        return asdict(TicketRecord(ticket_id, "billing", "open", "Customer reports a duplicate subscription charge."))


def cached_record(ticket_id: str) -> dict:
    if ticket_id != "T-101":
        raise TerminalFailure("cache_miss")
    return asdict(TicketRecord(ticket_id, "billing", "waiting_for_details", "Customer reports a duplicate subscription charge."))


def lookup_ticket(ticket_id: str, *, scenario: str = "healthy", policy: RetryPolicy = RetryPolicy(),
                  use_cache: bool = True, sleep: Callable = time.sleep,
                  jitter: Callable = random.random) -> RecoveryResult:
    validate_ticket_id(ticket_id)
    if type(use_cache) is not bool:
        raise ValueError("use_cache must be a boolean")
    service = DemoService(scenario)
    return recover(lambda: service.lookup(ticket_id), lambda v: validate_record(v, ticket_id),
                   policy=policy, fallback=(lambda: cached_record(ticket_id)) if use_cache else None,
                   sleep=sleep, jitter=jitter)


NEXT_STEPS = {
    "request_invoice_details": "Please share the invoice reference and the two charge dates for review.",
    "request_error_details": "Please share the error message and app version for review.",
    "ask_human_review": "Please ask a support representative to review this ticket.",
}


def default_next_step(record: TicketRecord) -> str:
    return "request_invoice_details" if record.category == "billing" else "request_error_details"


def render_reply(ticket_id: str, lookup: RecoveryResult, next_step: str | None = None) -> str:
    if lookup.value is None:
        return f"Demo ticket {ticket_id} could not be retrieved. Human review is needed; no status is confirmed."
    record = lookup.value
    if next_step is None:
        next_step = default_next_step(record)
    notice = ("Older cached demo snapshot; current status is unverified. " if lookup.status == "degraded"
              else "Primary demo snapshot. ")
    return (f"{notice}{record.ticket_id}: {record.status}. {record.summary} "
            f"{NEXT_STEPS[next_step]} No real account was checked or changed.")


@dataclass(frozen=True)
class SupportResult:
    ticket_id: str
    lookup: RecoveryResult
    message: str
    model_selection: RecoveryResult | None = None
    source: str = "simulated demo data"


def run_support(ticket_id: str = "T-101", **kwargs) -> SupportResult:
    lookup = lookup_ticket(ticket_id, **kwargs)
    return SupportResult(ticket_id, lookup, render_reply(ticket_id, lookup))


def print_run(result: SupportResult) -> None:
    print("Ticket:", result.ticket_id)
    for event in result.lookup.events:
        line = f"{event.stage} attempt {event.attempt}: {event.outcome}"
        if event.code:
            line += f" ({event.code})"
        if event.delay_seconds is not None:
            line += f" | delay {event.delay_seconds:g}s"
        print(line)
    print("Lookup result:", result.lookup.status)
    print("Reply:", result.message)
    print("Simulated data and retry waits; no API call or real ticket update.")


if __name__ == "__main__":
    result = run_support(scenario="transient", sleep=lambda _: None, jitter=lambda: 1)
    print(json.dumps(asdict(result), indent=2))
