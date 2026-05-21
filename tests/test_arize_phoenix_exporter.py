import json

import httpx
import pytest

from geminilens.exporters.arize_phoenix import ArizePhoenixExporter
from geminilens.observer import Trace


def _trace() -> Trace:
    return Trace(
        trace_id="abc123",
        model="gemini-2.5-flash",
        started_at=1700000000.0,
        ended_at=1700000000.523,
        prompt="What is RLHF?",
        response="Reinforcement learning from human feedback.",
        input_tokens=100,
        output_tokens=50,
        cached_tokens=10,
        cost_usd=0.0001,
        latency_ms=523.4,
        tags={"agent": "research", "env": "prod"},
    )


def _find_attr(attrs, key):
    for a in attrs:
        if a["key"] == key:
            return a["value"]
    return None


def test_init_requires_endpoint(monkeypatch):
    monkeypatch.delenv("PHOENIX_ENDPOINT", raising=False)
    with pytest.raises(ValueError):
        ArizePhoenixExporter()


def test_local_phoenix_works_without_api_key():
    exp = ArizePhoenixExporter(endpoint="http://localhost:6006")
    assert exp.endpoint == "http://localhost:6006"
    assert exp.api_key == ""
    assert exp.project == "geminilens"


def test_span_carries_openinference_and_genai_semconv():
    exp = ArizePhoenixExporter(endpoint="http://localhost:6006", project="hackathon")
    span = exp._span(_trace())
    assert span["name"] == "gemini.call"
    assert span["kind"] == 3
    assert len(span["traceId"]) == 32
    assert len(span["spanId"]) == 16
    attrs = span["attributes"]
    # OpenInference fields Phoenix UI cares about
    assert _find_attr(attrs, "openinference.span.kind")["stringValue"] == "LLM"
    assert _find_attr(attrs, "llm.model_name")["stringValue"] == "gemini-2.5-flash"
    assert _find_attr(attrs, "llm.token_count.prompt")["intValue"] == "100"
    assert _find_attr(attrs, "llm.token_count.completion")["intValue"] == "50"
    assert _find_attr(attrs, "llm.token_count.total")["intValue"] == "150"
    assert _find_attr(attrs, "llm.token_count.prompt.cache_read")["intValue"] == "10"
    assert _find_attr(attrs, "input.value")["stringValue"] == "What is RLHF?"
    assert "Reinforcement learning" in _find_attr(attrs, "output.value")["stringValue"]
    # Gen-AI semconv (for generic OTel pipelines)
    assert _find_attr(attrs, "gen_ai.system")["stringValue"] == "google.gemini"
    assert _find_attr(attrs, "gen_ai.usage.cost_usd")["doubleValue"] == pytest.approx(0.0001)
    # Tags propagate
    assert _find_attr(attrs, "tag.agent")["stringValue"] == "research"


def test_error_trace_marks_status_error():
    exp = ArizePhoenixExporter(endpoint="http://localhost:6006")
    tr = _trace()
    tr.error = "RuntimeError: api refused"
    span = exp._span(tr)
    assert span["status"]["code"] == 2
    assert span["status"]["message"] == "RuntimeError: api refused"


def test_export_posts_otlp_to_phoenix_v1_traces(monkeypatch):
    captured: dict = {}

    def fake_post(self, url, headers=None, content=None, **kw):
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = json.loads(content)
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    exp = ArizePhoenixExporter(
        endpoint="http://localhost:6006",
        project="hackathon-demo",
    )
    n = exp.export([_trace(), _trace(), _trace()])
    assert n == 3
    assert captured["url"] == "http://localhost:6006/v1/traces"
    # No Authorization header when no API key (local Phoenix)
    assert "Authorization" not in captured["headers"]
    assert captured["headers"]["x-phoenix-project-name"] == "hackathon-demo"
    body = captured["body"]
    rs = body["resourceSpans"][0]
    project_attr = next(a for a in rs["resource"]["attributes"]
                        if a["key"] == "openinference.project.name")
    assert project_attr["value"]["stringValue"] == "hackathon-demo"
    spans = rs["scopeSpans"][0]["spans"]
    assert len(spans) == 3


def test_arize_cloud_includes_bearer_auth(monkeypatch):
    captured: dict = {}

    def fake_post(self, url, headers=None, content=None, **kw):
        captured["headers"] = headers
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    exp = ArizePhoenixExporter(
        endpoint="https://app.phoenix.arize.com",
        api_key="px_secret_xyz",
    )
    exp.export([_trace()])
    assert captured["headers"]["Authorization"] == "Bearer px_secret_xyz"


def test_export_empty_is_noop(monkeypatch):
    called = {"n": 0}

    def fake_post(self, *a, **kw):
        called["n"] += 1
        return httpx.Response(200, request=httpx.Request("POST", "http://x"))

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    exp = ArizePhoenixExporter(endpoint="http://localhost:6006")
    assert exp.export([]) == 0
    assert called["n"] == 0
