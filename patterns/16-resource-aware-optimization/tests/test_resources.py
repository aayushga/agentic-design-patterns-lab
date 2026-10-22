"""Offline budget and cache behavior, using a controlled monotonic clock."""
import importlib

import pytest

app = importlib.import_module("patterns.16-resource-aware-optimization.app")
BRIEF = app.WorkItem("Report a login problem.")
DETAILED = app.WorkItem(BRIEF.query, "detailed")


class Clock:
    def __init__(self):
        self.now = 0.0
    def __call__(self):
        return self.now
    def advance(self, seconds):
        self.now += seconds


def test_brief_and_detailed_choose_different_profiles():
    brief = app.ResourceAwareAgent().answer(BRIEF)
    detailed = app.ResourceAwareAgent().answer(DETAILED)
    assert (brief.status, brief.selected_profile, brief.reserved_output_tokens) == ("answered", "economy", 600)
    assert (detailed.status, detailed.selected_profile, detailed.reserved_output_tokens) == ("answered", "thorough", 1600)
    assert len(detailed.answer) > len(brief.answer)


def test_budget_downgrade_is_explicit_and_strict_detail_blocks():
    agent = app.ResourceAwareAgent(app.Budget(output_tokens=600))
    result = agent.answer(DETAILED)
    assert result.status == "degraded" and result.selected_profile == "economy"
    assert any("output-token" in step for step in result.trace)
    strict = app.ResourceAwareAgent(app.Budget(output_tokens=600)).answer(DETAILED, allow_degraded=False)
    assert strict.status == "blocked" and strict.calls_made == 0 and not strict.answer


def test_time_forecast_can_select_economy_even_with_plenty_of_tokens():
    agent = app.ResourceAwareAgent(app.Budget(seconds=2), clock=Clock())
    result = agent.answer(DETAILED)
    assert result.status == "degraded" and result.reserved_output_tokens == 600
    assert any("forecast" in step for step in result.trace)


@pytest.mark.parametrize("budget", [app.Budget(output_tokens=599), app.Budget(max_calls=0), app.Budget(seconds=0.5)])
def test_no_eligible_profile_never_calls_backend(budget):
    def forbidden(*args):
        pytest.fail("No backend should be admitted")
    result = app.ResourceAwareAgent(budget, backend=forbidden, clock=Clock()).answer(BRIEF)
    assert result.status == "blocked" and result.calls_made == 0
    assert result.reserved_output_tokens == 0 and result.answer == ""


def test_reserves_before_call_and_does_not_refund_failures():
    def failure(item, profile, timeout):
        assert agent.calls == 1 and agent.reserved == 600
        raise RuntimeError("private token in backend exception")
    agent = app.ResourceAwareAgent(app.Budget(output_tokens=600, max_calls=2), backend=failure)
    failed = agent.answer(BRIEF)
    assert failed.status == "failed" and failed.remaining_output_tokens == 0
    assert "private" not in str(failed)
    assert agent.answer(BRIEF).status == "blocked"


def test_known_unavailable_thorough_can_fall_back_once_with_remaining_resources():
    seen = []
    def backend(item, profile, timeout):
        seen.append(profile.name)
        if profile == app.THOROUGH:
            raise app.BackendUnavailable()
        return "Request human review."
    result = app.ResourceAwareAgent(backend=backend).answer(DETAILED)
    assert seen == ["thorough", "economy"]
    assert result.status == "degraded" and result.calls_made == 2
    assert result.reserved_output_tokens == 2200 and result.remaining_output_tokens == 0


@pytest.mark.parametrize("budget,strict", [(app.Budget(output_tokens=1600), False),
    (app.Budget(max_calls=1), False), (app.Budget(), True)])
def test_unavailability_does_not_bypass_budget_or_strict_detail(budget, strict):
    calls = []
    def unavailable(item, profile, timeout):
        calls.append(profile.name)
        raise app.BackendUnavailable()
    result = app.ResourceAwareAgent(budget, backend=unavailable).answer(DETAILED, allow_degraded=not strict)
    assert calls == ["thorough"] and result.status == "unavailable"
    assert result.reserved_output_tokens == 1600 and not result.answer


def test_economy_unavailability_does_not_retry():
    def unavailable(*args):
        raise app.BackendUnavailable()
    result = app.ResourceAwareAgent(backend=unavailable).answer(BRIEF)
    assert result.status == "unavailable" and result.calls_made == 1


@pytest.mark.parametrize("value", [None, 12, "", " ", "x" + " " * 3000])
def test_invalid_raw_output_is_not_returned_or_cached(value):
    agent = app.ResourceAwareAgent(backend=lambda *args: value)
    result = agent.answer(BRIEF)
    assert result.status == "failed" and not result.answer and not agent.cache
    assert result.reserved_output_tokens == 600


def test_exact_raw_answer_boundary_is_accepted():
    value = " " + "x" * 2998 + " "
    assert app.validate_answer(value) == value


def test_late_response_is_discarded_and_deadline_prevents_further_calls():
    clock = Clock()
    def slow(*args):
        clock.advance(2)
        return "Late advice."
    agent = app.ResourceAwareAgent(app.Budget(seconds=2), backend=slow, clock=clock)
    result = agent.answer(BRIEF)
    assert result.status == "deadline_exceeded" and not result.answer and not agent.cache
    assert result.reserved_output_tokens == 600
    assert agent.answer(DETAILED).calls_made == 0


def test_timeout_passed_to_backend_is_remaining_time_capped_at_30():
    seen = []
    agent = app.ResourceAwareAgent(app.Budget(seconds=100), backend=lambda i, p, t: seen.append(t) or "Advice.", clock=Clock())
    agent.answer(BRIEF)
    assert seen == [30.0]


def test_fallback_rechecks_elapsed_time():
    clock = Clock()
    calls = []
    def unavailable(item, profile, timeout):
        calls.append(profile.name)
        clock.advance(9.5)
        raise app.BackendUnavailable()
    result = app.ResourceAwareAgent(backend=unavailable, clock=clock).answer(DETAILED)
    assert calls == ["thorough"] and result.status == "unavailable"
    assert any("forecast" in step for step in result.trace)


def test_cache_hit_uses_no_new_call_or_reservation_even_after_allowance_spent():
    agent = app.ResourceAwareAgent(app.Budget(output_tokens=600, max_calls=1))
    first = agent.answer(BRIEF)
    cached = agent.answer(BRIEF)
    assert cached.status == "cached" and cached.cache_hit and cached.answer == first.answer
    assert cached.calls_made == cached.reserved_output_tokens == 0
    assert cached.session_calls == 1 and cached.session_reserved_output_tokens == 600


def test_cache_does_not_cross_query_detail_session_or_degradation_boundaries():
    agent = app.ResourceAwareAgent(app.Budget(output_tokens=600))
    assert agent.answer(DETAILED).status == "degraded"
    assert agent.answer(DETAILED, allow_degraded=False).status == "blocked"
    assert agent.answer(BRIEF).status == "blocked"
    assert app.ResourceAwareAgent(app.Budget(output_tokens=0)).answer(BRIEF).status == "blocked"
    other = app.ResourceAwareAgent(app.Budget(output_tokens=2200, max_calls=2))
    other.answer(BRIEF)
    detailed = other.answer(DETAILED)
    assert detailed.status == "answered" and not detailed.cache_hit


def test_expired_session_does_not_serve_cache():
    clock = Clock()
    agent = app.ResourceAwareAgent(clock=clock)
    agent.answer(BRIEF)
    clock.advance(11)
    assert agent.answer(BRIEF).status == "deadline_exceeded"


def test_lru_cache_is_bounded_and_hits_refresh_recency():
    agent = app.ResourceAwareAgent(app.Budget(output_tokens=6000, max_calls=10), cache_size=2)
    a, b, c = [app.WorkItem(text) for text in ("A", "B", "C")]
    agent.answer(a)
    agent.answer(b)
    agent.answer(a)
    agent.answer(c)
    assert list(agent.cache) == [a, c]
    assert agent.answer(b).calls_made == 1
    assert agent.calls == 4 and len(agent.cache) == 2


def test_cache_can_be_disabled():
    agent = app.ResourceAwareAgent(cache_size=0)
    assert agent.answer(BRIEF).calls_made == agent.answer(BRIEF).calls_made == 1
    assert not agent.cache


def test_many_requests_never_exceed_shared_limits():
    agent = app.ResourceAwareAgent(app.Budget(output_tokens=1800, max_calls=2))
    results = [agent.answer(app.WorkItem(f"Request {i}")) for i in range(10)]
    assert sum(r.calls_made for r in results) == 2
    assert agent.reserved == 1200 and agent.calls == 2
    assert all(r.remaining_output_tokens >= 0 for r in results)


@pytest.mark.parametrize("kwargs", [{"output_tokens": -1}, {"output_tokens": True}, {"output_tokens": 1.2},
    {"output_tokens": 100001}, {"max_calls": -1}, {"max_calls": True}, {"max_calls": 11},
    {"seconds": 0}, {"seconds": True}, {"seconds": float("nan")}, {"seconds": float("inf")}, {"seconds": 301}])
def test_invalid_budget_is_rejected(kwargs):
    with pytest.raises(ValueError):
        app.Budget(**kwargs)


@pytest.mark.parametrize("query,detail", [(None, "brief"), ("", "brief"), (" ", "brief"),
    ("a" * 1001, "brief"), ("Valid", "unknown")])
def test_invalid_work_item_is_rejected(query, detail):
    with pytest.raises(ValueError):
        app.WorkItem(query, detail)
