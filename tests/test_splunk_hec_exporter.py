import json

import httpx
import pytest

from geminilens.exporters.splunk_hec import SplunkHECExporter
from geminilens.observer import Trace, ToolCall


def _trace() -> Trace:
    return Trace(
        trace_id="abc123",
        model="gemini-2.5-flash",
        started_at=1700000000.0,
        ended_at=1700000000.523,
        prompt="search Splunk for 500s on /checkout",
        response="found 47 events in last hour",
        input_tokens=120,
        output_tokens=60,
        cached_tokens=20,
        cost_usd=0.00012,
        latency_ms=812.0,
        tool_calls=[
            ToolCall(name="splunk_search", args={"spl": "..."}, result={"count": 47}, duration_ms=412.0),
            ToolCall(name="format_report", args={}, result={}, duration_ms=23.0),
        ],
        tags={"agent": "sre-bot", "env": "prod"},
    )


def test_init_requires_credentials(monkeypatch):
    monkeypatch.delenv("SPLUNK_HEC_URL", raising=False)
    monkeypatch.delenv("SPLUNK_HEC_TOKEN", raising=False)
    with pytest.raises(ValueError):
        SplunkHECExporter()


def test_event_envelope_shape_is_splunk_hec_compatible():
    exp = SplunkHECExporter(
        url="https://splunk.example.com:8088",
        token="t-12345",
        index="ai_agents",
        sourcetype="geminilens:trace",
    )
    e = exp._event(_trace())
    assert e["time"] == 1700000000.0
    assert e["index"] == "ai_agents"
    assert e["sourcetype"] == "geminilens:trace"
    assert e["source"] == "geminilens"
    ev = e["event"]
    assert ev["trace_id"] == "abc123"
    assert ev["model"] == "gemini-2.5-flash"
    assert ev["system"] == "google.gemini"
    assert ev["input_tokens"] == 120
    assert ev["output_tokens"] == 60
    assert ev["cached_tokens"] == 20
    assert ev["cost_usd"] == pytest.approx(0.00012)
    assert ev["latency_ms"] == pytest.approx(812.0)
    assert ev["tool_calls"] == 2
    assert "splunk_search" in ev["tool_call_names"]
    assert ev["tags"]["agent"] == "sre-bot"
    assert "search Splunk" in ev["prompt"]


def test_error_trace_carries_error_field():
    exp = SplunkHECExporter(url="https://splunk.example.com:8088", token="t")
    tr = _trace()
    tr.error = "Splunk 504 gateway timeout"
    e = exp._event(tr)
    assert e["event"]["error"] == "Splunk 504 gateway timeout"


def test_export_posts_to_hec_collector_url(monkeypatch):
    captured: dict = {}

    def fake_post(self, url, headers=None, content=None, **kw):
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = content
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    exp = SplunkHECExporter(url="https://splunk.example.com:8088", token="t-abc")
    n = exp.export([_trace(), _trace()])
    assert n == 2
    assert captured["url"] == "https://splunk.example.com:8088/services/collector/event"
    assert captured["headers"]["Authorization"] == "Splunk t-abc"
    # HEC body is newline-delimited JSON, not a JSON array
    lines = [ln for ln in captured["body"].split("\n") if ln.strip()]
    assert len(lines) == 2
    for ln in lines:
        obj = json.loads(ln)
        assert obj["event"]["model"] == "gemini-2.5-flash"


def test_export_empty_is_noop(monkeypatch):
    called = {"n": 0}

    def fake_post(self, *a, **kw):
        called["n"] += 1
        return httpx.Response(200, request=httpx.Request("POST", "http://x"))

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    exp = SplunkHECExporter(url="https://splunk.example.com:8088", token="t")
    assert exp.export([]) == 0
    assert called["n"] == 0
