"""Real SDK serialization/cleanup against an in-memory HTTP transport only."""
import asyncio
from dataclasses import asdict
from importlib import import_module
import json
from pathlib import Path

import pytest

sdk = pytest.importorskip("openai", reason="Install optional SDK requirements for HTTP contract tests")
httpx = pytest.importorskip("httpx")
ROOT = Path(__file__).resolve().parents[2]


def module(number, optional=False):
    folder = next((ROOT / "patterns").glob(f"{number:02d}-*"))
    stem = next((folder / "openai_version").glob("*.py")).stem if optional else "app"
    return import_module(f"patterns.{folder.name}." + (f"openai_version.{stem}" if optional else stem))


def response(text=None, *, call=None):
    output = ([{"type":"function_call", "id":"fc_offline", "call_id":"call_offline",
                "name":call[0], "arguments":json.dumps(call[1]), "status":"completed"}] if call else
              [{"type":"message", "id":"msg_offline", "role":"assistant", "status":"completed",
                "content":[{"type":"output_text", "text":text, "annotations":[]}]}])
    return {"id":"resp_offline", "object":"response", "created_at":0, "status":"completed",
            "model":"gpt-6-astra", "output":output}


@pytest.fixture
def transport(monkeypatch):
    real_sync, real_async = sdk.OpenAI, sdk.AsyncOpenAI
    def install(handler):
        requests, clients, options = [], [], []
        def dispatch(request):
            data = json.loads(request.content)
            requests.append(data)
            return handler(data, len(requests)-1)
        def sync_factory(**kwargs):
            options.append(kwargs)
            client = real_sync(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(dispatch)))
            clients.append(client)
            return client
        def async_factory(**kwargs):
            options.append(kwargs)
            client = real_async(**kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(dispatch)))
            clients.append(client)
            return client
        monkeypatch.setattr(sdk,"OpenAI",sync_factory)
        monkeypatch.setattr(sdk,"AsyncOpenAI",async_factory)
        monkeypatch.setenv("OPENAI_API_KEY","offline-placeholder")
        return requests, clients, options
    return install


def scenario(number, tmp_path):
    """Give each real adapter enough valid output to finish its host workflow."""
    app, api = module(number), module(number,True)
    if number == 1:
        return lambda: api.run_prompt_chain("Support quality"), ["Summary", '["quality"]', '{"recommended_next_step":"Review"}']
    if number == 2:
        return lambda: api.route_with_openai("Invoice question"), ['{"route":"billing","confidence":"high","reason":"Invoice"}']
    if number == 3:
        return lambda: asyncio.run(api.run_openai_parallel("Support issue")), ["Analysis"]*3
    if number == 4:
        return lambda: api.run_openai_reflection("Issue",max_revisions=0), ["Draft", '{"approved":true,"issues":[]}']
    if number == 5:
        return lambda: api.run_openai_tool_use("Status of ORD-1001",max_tool_calls=1), [response(call=("lookup_order",{"order_id":"ORD-1001"})),"Demo order shipped"]
    if number == 6:
        plan = app.local_planner(app.PlanningRequest("offsite",20,600),set(),set())
        return lambda: api.run_openai_planning("offsite"), [json.dumps(asdict(plan))]
    if number == 7:
        return lambda: api.run_openai_collaboration("Invoice issue"), ['{"roles":["billing"],"reason":"Invoice"}',
            '{"findings":[{"evidence":"Invoice issue","assessment":"Reported concern","next_step":"Share invoice"}]}',"Human review needed"]
    if number == 8:
        def run():
            with app.MemoryStore(tmp_path/"memory.sqlite3") as store:
                return api.run_openai_turn("issue: crash",app.Session("u","s"),store)
        return run, ["Please share the error message"]
    if number == 9:
        return lambda: api.run_openai_adaptation("Crash","technical",app.AdaptivePolicy()), ['{"strategy":"brief","acknowledgement":"Thanks","next_steps":["Share error"]}']
    if number == 10:
        pytest.importorskip("mcp")
        return lambda: asyncio.run(api.run_openai_mcp("Read T-101",max_tool_calls=1)), [response(call=("get_ticket",{"ticket_id":"T-101"})),"Fictional ticket report"]
    if number == 11:
        return lambda: api.run_openai_goal((app.Ticket("T-1"),),app.Goal(("T-1",))), ['{"kind":"triage","ticket_id":"T-1"}']
    if number == 12:
        return lambda: api.run_openai_recovery(sleep=lambda _:None), ['{"ticket_id":"T-101","next_step":"request_invoice_details"}']
    if number == 13:
        return lambda: api.draft_for_review("Issue",app.ReviewQueue()), ['{"draft":"Please share details for review"}']
    if number == 14:
        hits = app.KnowledgeBase(app.load_documents()).retrieve("Within how many days can I request a refund?")
        value = {"status":"answered","answer":"Fictional policy excerpt","citations":[{"chunk_id":hits[0].chunk.chunk_id,"quote":hits[0].chunk.text}]}
        return lambda: api.run_openai_rag("Within how many days can I request a refund?"), [json.dumps(value)]
    if number == 15:
        pytest.importorskip("a2a")
        async def run():
            async with api.openai_session() as coordinator:
                return await coordinator.send({"skill":app.SKILL,"category":"support","issue":"Crash"})
        return lambda:asyncio.run(run()), ['{"priority":"normal","summary":"Crash reported","next_step":"Request details"}']
    if number == 16:
        def run():
            with api.openai_agent(app.Budget(seconds=100)) as agent:
                return agent.answer(app.WorkItem("Invoice issue"))
        return run,["Ask billing to review the invoice"]
    if number == 17:
        return api.run_openai_reasoning,['{"candidates":["8/(3-8/3)"]}']
    if number == 18:
        return lambda:api.run_openai_guarded("Order status"), ['{"action":"lookup_order","order_id":"ORD-101"}']
    if number == 19:
        return api.run_openai_evaluation,['{"route":"billing"}','{"route":"billing"}','{"route":"support"}']
    if number == 20:
        return api.run_openai_prioritization,['{"ranked_task_ids":["metrics","notes","feedback"]}']
    return api.run_openai_discovery,['{"config_id":"cfg-01"}','{"config_id":"cfg-03"}']


@pytest.mark.parametrize("number",range(1,22))
def test_every_adapter_serializes_bounded_requests_and_closes_clients(number,tmp_path,transport):
    # A2A is imported by its app; skip just that case when its separate SDK is absent.
    if number == 15:
        pytest.importorskip("a2a")
    run, outputs = scenario(number,tmp_path)
    def handler(data,index):
        assert index < len(outputs), "Unexpected extra model request"
        item = outputs[index]
        return httpx.Response(200,json=item if isinstance(item,dict) else response(item))
    requests, clients, options = transport(handler)
    result = run()
    assert result is not None and len(requests) == len(outputs)
    assert clients and all(client.is_closed() for client in clients)
    assert all(option["max_retries"] == 0 and 0 < option["timeout"] <= 30 for option in options)
    assert all(request["store"] is False and 0 < request["max_output_tokens"] <= 2500 for request in requests)
    if number in (5,10):
        assert any(item.get("type") == "function_call_output" and item["call_id"] == "call_offline"
                   for item in requests[1]["input"])
    if number == 13:
        assert result.state == "pending" and result.approved_revision is None
    if number == 19:
        assert result.metrics["coverage"] == .375 and result.metrics["accuracy"] == 1
    if number == 21:
        assert result.report.best_latency_ms == 45 and result.report.target_met


@pytest.mark.parametrize("number",[1,2])
def test_early_adapters_do_not_retry_a_server_error_and_close(number,tmp_path,transport):
    run,_ = scenario(number,tmp_path)
    requests,clients,_ = transport(lambda *_:httpx.Response(500,json={"error":{"message":"PRIVATE_SERVER_ERROR","type":"server_error"}}))
    with pytest.raises(sdk.InternalServerError):
        run()
    assert len(requests) == 1 and all(client.is_closed() for client in clients)
