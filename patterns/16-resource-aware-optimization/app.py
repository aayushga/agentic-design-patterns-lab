"""Choose a response profile within a shared call, output-token, and time budget."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import asdict, dataclass
import json
import math
import time
from typing import Callable


@dataclass(frozen=True)
class WorkItem:
    query: str
    detail: str = "brief"

    def __post_init__(self):
        if not isinstance(self.query, str) or not 1 <= len(self.query) <= 1000 or not self.query.strip():
            raise ValueError("query must contain text and be at most 1000 characters")
        if self.detail not in ("brief", "detailed"):
            raise ValueError("detail must be brief or detailed")


@dataclass(frozen=True)
class Budget:
    output_tokens: int = 2200
    max_calls: int = 2
    seconds: float = 10.0

    def __post_init__(self):
        if type(self.output_tokens) is not int or not 0 <= self.output_tokens <= 100000:
            raise ValueError("output_tokens must be an integer from 0 to 100000")
        if type(self.max_calls) is not int or not 0 <= self.max_calls <= 10:
            raise ValueError("max_calls must be an integer from 0 to 10")
        if (isinstance(self.seconds, bool) or not isinstance(self.seconds, (int, float))
                or not 0 < self.seconds <= 300 or not math.isfinite(self.seconds)):
            raise ValueError("seconds must be finite and between 0 (exclusive) and 300")


@dataclass(frozen=True)
class Profile:
    name: str
    detail: str
    max_output_tokens: int
    reasoning_effort: str
    expected_seconds: float


ECONOMY = Profile("economy", "brief", 600, "low", 1.0)
THOROUGH = Profile("thorough", "detailed", 1600, "medium", 3.0)
Backend = Callable[[WorkItem, Profile, float], str]


class BackendUnavailable(Exception):
    """A known transient failure; a lower-resource alternative may be attempted."""


@dataclass(frozen=True)
class Result:
    query: str
    requested_detail: str
    status: str
    selected_profile: str | None
    answer: str
    cache_hit: bool
    calls_made: int
    reserved_output_tokens: int
    session_calls: int
    session_reserved_output_tokens: int
    remaining_output_tokens: int
    elapsed_seconds: float
    trace: tuple[str, ...]


def validate_answer(value: object) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 3000 or not value.strip():
        raise ValueError("Answer must contain text and be at most 3000 raw characters")
    return value


def local_backend(item: WorkItem, profile: Profile, timeout: float) -> str:
    """Fixed fictional support guidance; token allowances are simulated locally."""
    query = item.query.casefold()
    if "invoice" in query or "billing" in query:
        brief = "Collect the invoice reference and ask billing to review it. No refund is approved."
        detail = "Compare the invoice date, reference, and amount with your records before requesting billing review. Do not treat a duplicate-looking invoice as a confirmed duplicate charge."
    elif "login" in query or "password" in query:
        brief = "Record the exact error and request support review. No account change is performed."
        detail = "First collect the error and approximate time. Compare a documented password-reset attempt with escalation to support: self-service may be quicker, while support can review persistent failures. Never share passwords or reset tokens."
    else:
        brief = "Describe the issue and request human support review. No account action is performed."
        detail = "Collect the observed behavior, expected behavior, and reproduction steps. Compare available documented self-service guidance with human escalation; account-specific decisions require review."
    return brief if profile.detail == "brief" else brief + " " + detail


class ResourceAwareAgent:
    """Single-threaded, session-scoped controller with conservative reservations."""

    def __init__(self, budget: Budget = Budget(), *, backend: Backend = local_backend,
                 clock: Callable[[], float] = time.monotonic, cache_size: int = 8):
        if not isinstance(budget, Budget) or not callable(backend) or not callable(clock):
            raise ValueError("Provide a Budget and callable backend/clock")
        if type(cache_size) is not int or not 0 <= cache_size <= 32:
            raise ValueError("cache_size must be an integer from 0 to 32")
        self.budget, self.backend, self.clock = budget, backend, clock
        self.cache_size = cache_size
        self.started = clock()
        self.deadline = self.started + budget.seconds
        self.calls = 0
        self.reserved = 0
        self.cache: OrderedDict[WorkItem, tuple[Profile, str]] = OrderedDict()

    def answer(self, item: WorkItem, *, allow_degraded: bool = True) -> Result:
        if not isinstance(item, WorkItem) or type(allow_degraded) is not bool:
            raise ValueError("Provide a WorkItem and a boolean allow_degraded")
        calls_before, tokens_before = self.calls, self.reserved
        trace: list[str] = []

        def finish(status: str, profile: Profile | None = None, text: str = "", *, cached=False) -> Result:
            return Result(item.query, item.detail, status, profile.name if profile else None,
                          text, cached, self.calls - calls_before, self.reserved - tokens_before,
                          self.calls, self.reserved, self.budget.output_tokens - self.reserved,
                          round(max(0.0, self.clock() - self.started), 3), tuple(trace))

        if self.clock() >= self.deadline:
            trace.append("session deadline reached")
            return finish("deadline_exceeded")
        if item in self.cache:
            profile, text = self.cache[item]
            self.cache.move_to_end(item)
            trace.append("exact query and requested detail found in session cache")
            return finish("cached", profile, text, cached=True)

        profiles = [ECONOMY] if item.detail == "brief" else [THOROUGH]
        if item.detail == "detailed" and allow_degraded:
            profiles.append(ECONOMY)
        attempted = False
        for profile in profiles:
            remaining_seconds = self.deadline - self.clock()
            if remaining_seconds <= 0:
                trace.append("session deadline reached")
                return finish("deadline_exceeded")
            if self.calls >= self.budget.max_calls:
                trace.append(f"skip {profile.name}: call limit")
                continue
            if self.reserved + profile.max_output_tokens > self.budget.output_tokens:
                trace.append(f"skip {profile.name}: output-token allowance")
                continue
            if profile.expected_seconds > remaining_seconds:
                trace.append(f"skip {profile.name}: forecast exceeds remaining time")
                continue
            # Reserve before calling. Never refund on errors, incomplete output,
            # or missing usage: the provider may already have performed work.
            self.calls += 1
            self.reserved += profile.max_output_tokens
            attempted = True
            trace.append(f"reserve {profile.max_output_tokens} output tokens for {profile.name}")
            try:
                text = validate_answer(self.backend(item, profile, min(30.0, remaining_seconds)))
            except BackendUnavailable:
                trace.append(f"{profile.name} temporarily unavailable; reservation retained")
                continue
            except Exception:
                trace.append(f"{profile.name} failed or returned invalid output; reservation retained")
                return finish("failed", profile)
            if self.clock() >= self.deadline:
                trace.append("response arrived after the deadline; not cached or returned")
                return finish("deadline_exceeded", profile)
            degraded = profile.detail != item.detail
            if degraded:
                trace.append("brief response supplied instead of requested detailed response")
            elif self.cache_size:
                self.cache[item] = (profile, text)
                self.cache.move_to_end(item)
                while len(self.cache) > self.cache_size:
                    self.cache.popitem(last=False)
            return finish("degraded" if degraded else "answered", profile, text)
        return finish("unavailable" if attempted else "blocked")


def demo() -> None:
    print("Free local simulation: allowances are not actual model usage or dollar costs.")
    agent = ResourceAwareAgent()
    item = WorkItem("Compare recovery options for a login problem.", "detailed")
    print(json.dumps(asdict(agent.answer(item)), indent=2))
    print(json.dumps(asdict(agent.answer(item)), indent=2))


if __name__ == "__main__":
    demo()
