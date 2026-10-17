"""SDK failures and output errors are simulated; no SDK or API key is needed."""
from dataclasses import asdict
from datetime import datetime, timezone
import importlib
import json
import sys
from types import SimpleNamespace as NS

import pytest

module = importlib.import_module("patterns.12-exception-handling-and-recovery.openai_version.openai_recovery")
app = importlib.import_module("patterns.12-exception-handling-and-recovery.app")


class ConnectionFailure(Exception):
    pass


class TimeoutFailure(ConnectionFailure):
    pass


class StatusFailure(Exception):
    def __init__(self, status, code=None, headers=None):
        super().__init__("Sensitive raw service diagnostic: do not expose")
        self.status_code, self.code = status, code
        self.response = NS(headers=headers or {})


def selection(step="request_invoice_details", ticket_id="T-101"):
    return NS(status="completed", output_text=json.dumps({"ticket_id": ticket_id, "next_step": step}))


def failed_response(code):
    return NS(status="failed", output_text="",
              error=NS(code=code, message="Sensitive raw generation diagnostic: do not expose"))


@pytest.fixture
def sdk(monkeypatch):
    def install(*outcomes):
        pending, requests, clients = iter(outcomes), [], []
        class Client:
            def __init__(self, **kwargs):
                self.state = {"options": kwargs, "closed": False}
                clients.append(self.state)
                self.responses = NS(create=self.create)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.state["closed"] = True
            def create(self, **kwargs):
                requests.append(kwargs)
                output = next(pending)
                if isinstance(output, BaseException):
                    raise output
                return output
        fake = NS(OpenAI=Client, APIConnectionError=ConnectionFailure,
                  APITimeoutError=TimeoutFailure, APIStatusError=StatusFailure)
        monkeypatch.setitem(sys.modules, "openai", fake)
        monkeypatch.setenv("OPENAI_API_KEY", "offline-placeholder")
        return requests, clients
    return install


def execute(**kwargs):
    return module.run_openai_recovery(sleep=lambda _: None, jitter=lambda: 1, **kwargs)


def test_normal_request_contract_and_client_cleanup(sdk):
    requests, clients = sdk(selection())
    result = execute()
    assert result.model_selection.status == "success" and len(requests) == 1
    request = requests[0]
    assert request["model"] == "gpt-6-astra" and request["reasoning"] == {"effort": "low"}
    assert request["store"] is False and request["text"]["format"]["strict"] is True
    assert json.loads(request["input"])["source"] == "simulated demo data"
    assert clients[0]["closed"] and clients[0]["options"]["max_retries"] == 0
    assert clients[0]["options"]["timeout"] == 30


@pytest.mark.parametrize("error", [TimeoutFailure(), ConnectionFailure(), StatusFailure(500),
    StatusFailure(503), StatusFailure(408), StatusFailure(409), StatusFailure(429, "rate_limit_exceeded")])
def test_transient_sdk_errors_retry_once_then_recover(sdk, error):
    requests, clients = sdk(error, selection())
    result = execute()
    assert result.model_selection.status == "recovered" and len(requests) == 2
    assert clients[0]["closed"] and "Sensitive raw" not in json.dumps(asdict(result))


def test_exhausted_model_requests_use_local_rule_and_preserve_cache_warning(sdk):
    requests, clients = sdk(StatusFailure(503), StatusFailure(503))
    result = execute(scenario="outage")
    assert result.lookup.status == result.model_selection.status == "degraded"
    assert len(requests) == 2 and clients[0]["closed"]
    assert "Older cached" in result.message and "local rule" in result.message
    assert json.loads(requests[0]["input"])["lookup_status"] == "degraded"


@pytest.mark.parametrize("code,expected_code", [("server_error", "server_error"), ("rate_limit_exceeded", "rate_limited")])
def test_transient_failed_response_retries_before_fallback(sdk, code, expected_code):
    requests, clients = sdk(failed_response(code), selection())
    waits = []
    result = module.run_openai_recovery(sleep=waits.append, jitter=lambda: 1)
    recovery = result.model_selection
    assert recovery.status == "recovered" and recovery.primary_attempts == len(requests) == 2
    assert waits == [0.25] and recovery.events[0].code == expected_code
    assert all(e.stage == "primary" for e in recovery.events) and clients[0]["closed"]
    assert "Sensitive raw" not in json.dumps(asdict(result))


@pytest.mark.parametrize("code", ["server_error", "rate_limit_exceeded"])
@pytest.mark.parametrize("attempts", [1, 2])
def test_failed_response_exhausts_exact_budget_then_uses_local_rule(sdk, code, attempts):
    requests, clients = sdk(*(failed_response(code) for _ in range(attempts)))
    waits = []
    result = module.run_openai_recovery(model_policy=app.RetryPolicy(max_attempts=attempts),
                                      sleep=waits.append, jitter=lambda: 1)
    recovery = result.model_selection
    assert recovery.status == "degraded" and recovery.value == "request_invoice_details"
    assert recovery.primary_attempts == len(requests) == attempts and len(waits) == attempts - 1
    assert sum(e.stage == "fallback" for e in recovery.events) == 1 and clients[0]["closed"]
    assert "Sensitive raw" not in json.dumps(asdict(result))


@pytest.mark.parametrize("code", ["invalid_prompt", "unknown_future_error", None])
def test_non_transient_failed_response_does_not_retry(sdk, code):
    requests, clients = sdk(failed_response(code))
    result = execute()
    assert len(requests) == 1 and result.model_selection.status == "degraded" and clients[0]["closed"]
    assert result.model_selection.events[0].code == "incomplete_model_response"
    assert "Sensitive raw" not in json.dumps(asdict(result))


@pytest.mark.parametrize("error", [StatusFailure(401), StatusFailure(403), StatusFailure(400),
    StatusFailure(404), StatusFailure(422), StatusFailure(429, "insufficient_quota"),
    StatusFailure(429, "billing_hard_limit_reached"), StatusFailure(429)])
def test_terminal_sdk_error_never_retries_or_accepts_fallback(sdk, error):
    requests, clients = sdk(error)
    result = execute()
    assert result.model_selection.status == "unavailable" and result.model_selection.value is None
    assert len(requests) == 1 and len(result.model_selection.events) == 1 and clients[0]["closed"]
    assert "human review" in result.message and "Sensitive raw" not in json.dumps(asdict(result))


@pytest.mark.parametrize("raw", ["not JSON", "[]", "{}", '{"ticket_id":"T-999","next_step":"ask_human_review"}',
    '{"ticket_id":"T-101","next_step":"refund"}', '{"ticket_id":"T-101","next_step":"request_error_details"}',
    '{"ticket_id":"T-101","next_step":"ask_human_review","resolved":true}'])
def test_invalid_model_output_is_not_retried_and_uses_validated_local_rule(sdk, raw):
    requests, _ = sdk(NS(status="completed", output_text=raw))
    result = execute()
    assert len(requests) == 1 and result.model_selection.status == "degraded"
    assert result.model_selection.value == "request_invoice_details"


@pytest.mark.parametrize("status,text", [("incomplete", "partial"), ("failed", ""),
    ("completed", None), ("completed", ""), ("completed", " ")])
def test_unusable_response_degrades_honestly(sdk, status, text):
    requests, clients = sdk(NS(status=status, output_text=text))
    result = execute()
    assert len(requests) == 1 and result.model_selection.status == "degraded" and clients[0]["closed"]


def test_unexpected_sdk_bug_propagates_but_closes_client(sdk):
    requests, clients = sdk(RuntimeError("programming bug"))
    with pytest.raises(RuntimeError, match="programming bug"):
        execute()
    assert len(requests) == 1 and clients[0]["closed"]


def test_missing_key_is_configuration_error_before_lookup_or_client(sdk, monkeypatch):
    requests, clients = sdk()
    monkeypatch.delenv("OPENAI_API_KEY")
    monkeypatch.setattr(module, "lookup_ticket", lambda *args, **kwargs: pytest.fail("No lookup without configuration"))
    with pytest.raises(ValueError, match="Missing OPENAI_API_KEY"):
        execute()
    assert not requests and not clients


def test_unavailable_lookup_skips_model_without_importing_sdk(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "offline-placeholder")
    monkeypatch.setitem(sys.modules, "openai", None)
    result = execute(scenario="denied")
    assert result.lookup.status == "unavailable" and result.model_selection is None


@pytest.mark.parametrize("explicit,expected", [(None, "gpt-6.1-sol"), ("gpt-6-astra", "gpt-6-astra")])
def test_model_override_precedence(sdk, monkeypatch, explicit, expected):
    requests, _ = sdk(selection())
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6.1-sol")
    execute(model=explicit)
    assert requests[0]["model"] == expected


@pytest.mark.parametrize("headers,expected", [({"retry-after": "1.5"}, 1.5),
    ({"retry-after-ms": "500", "retry-after": "4"}, 0.5),
    ({"retry-after": "0"}, 0), ({"retry-after": "-1"}, None),
    ({"retry-after": "nan"}, None), ({"retry-after": "inf"}, None),
    ({"retry-after": "nonsense"}, None), ({}, None),
    ({"retry-after-ms": "bad", "retry-after": "1"}, 1)])
def test_retry_after_numeric_parsing(headers, expected):
    assert module.retry_after_seconds(headers) == expected


def test_http_date_retry_after():
    now = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)
    assert module.retry_after_seconds({"retry-after": "Fri, 16 Oct 2026 12:00:02 GMT"}, now=now) == 2
    assert module.retry_after_seconds({"retry-after": "Fri, 16 Oct 2026 11:59:59 GMT"}, now=now) == 0


def test_long_server_wait_uses_fallback_without_early_retry(sdk):
    requests, _ = sdk(StatusFailure(429, "rate_limit_exceeded", {"retry-after": "60"}))
    result = execute()
    assert len(requests) == 1 and result.model_selection.status == "degraded"
    assert any(e.outcome == "retry_deferred" for e in result.model_selection.events)


def test_server_wait_reaches_actual_retry_sleeper(sdk):
    requests, _ = sdk(StatusFailure(429, "slow_down", {"retry-after-ms": "1000"}), selection())
    waits = []
    result = module.run_openai_recovery(sleep=waits.append)
    assert result.model_selection.status == "recovered" and len(requests) == 2 and waits == [1]


def test_single_attempt_policy_never_makes_extra_request(sdk):
    requests, _ = sdk(TimeoutFailure())
    result = execute(model_policy=app.RetryPolicy(max_attempts=1))
    assert len(requests) == 1 and result.model_selection.status == "degraded"
