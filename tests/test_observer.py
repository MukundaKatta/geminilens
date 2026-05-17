import time

from geminilens.observer import GeminiObserver
from geminilens.store import TraceStore


def test_trace_records_latency_and_cost(tmp_path):
    store = TraceStore(tmp_path / "traces.jsonl")
    obs = GeminiObserver(store=store)
    with obs.trace("gemini-2.5-flash", prompt="hi") as tr:
        tr.input_tokens = 100
        tr.output_tokens = 50
        time.sleep(0.01)
    rec = store.recent()[-1]
    assert rec["input_tokens"] == 100
    assert rec["output_tokens"] == 50
    assert rec["latency_ms"] > 0
    assert rec["cost_usd"] > 0


def test_run_tool_captures_args_result_and_timing(tmp_path):
    store = TraceStore(tmp_path / "traces.jsonl")
    obs = GeminiObserver(store=store)
    with obs.trace("gemini-2.5-flash", prompt="q") as tr:
        result = obs.run_tool(tr, "add", lambda a, b: a + b, 2, 3)
    assert result == 5
    rec = store.recent()[-1]
    assert len(rec["tool_calls"]) == 1
    assert rec["tool_calls"][0]["name"] == "add"
    assert rec["tool_calls"][0]["error"] is None


def test_run_tool_captures_error(tmp_path):
    store = TraceStore(tmp_path / "traces.jsonl")
    obs = GeminiObserver(store=store)

    def boom():
        raise ValueError("nope")

    try:
        with obs.trace("gemini-2.5-flash") as tr:
            obs.run_tool(tr, "boom", boom)
    except ValueError:
        pass

    rec = store.recent()[-1]
    assert rec["tool_calls"][0]["error"].startswith("ValueError")
    assert rec["error"].startswith("ValueError")
