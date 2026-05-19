import json
import time

import httpx
import pytest

from geminilens.exporters.truefoundry import TrueFoundryExporter
from geminilens.observer import Trace


def _trace() -> Trace:
    return Trace(
        trace_id="abc123",
        model="gemini-2.5-flash",
        started_at=1700000000.0,
        ended_at=1700000000.523,
        prompt="hi",
        response="hello",
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


def test_init_requires_credentials(monkeypatch):
    monkeypatch.delenv("TFY_ENDPOINT", raising=False)
    monkeypatch.delenv("TFY_API_KEY", raising=False)
    with pytest.raises(ValueError):
        TrueFoundryExporter()


def test_span_shape_carries_genai_semconv():
    exp = TrueFoundryExporter(endpoint="https://x.truefoundry.cloud", api_key="t")
    span = exp._span(_trace())
    assert span["name"] == "gemini.call"
    assert span["kind"] == 3
    assert len(span["traceId"]) == 32
    assert len(span["spanId"]) == 16
    attrs = span["attributes"]
    assert _find_attr(attrs, "gen_ai.system")["stringValue"] == "google.gemini"
    assert _find_attr(attrs, "gen_ai.request.model")["stringValue"] == "gemini-2.5-flash"
    assert _find_attr(attrs, "gen_ai.usage.input_tokens")["intValue"] == "100"
    assert _find_attr(attrs, "gen_ai.usage.output_tokens")["intValue"] == "50"
    assert _find_attr(attrs, "gen_ai.usage.cached_tokens")["intValue"] == "10"
    assert _find_attr(attrs, "gen_ai.usage.cost_usd")["doubleValue"] == pytest.approx(0.0001)
    assert _find_attr(attrs, "tag.agent")["stringValue"] == "research"


def test_error_trace_marks_status_error():
    exp = TrueFoundryExporter(endpoint="https://x.truefoundry.cloud", api_key="t")
    tr = _trace()
    tr.error = "RuntimeError: boom"
    span = exp._span(tr)
    assert span["status"]["code"] == 2
    assert span["status"]["message"] == "RuntimeError: boom"


def test_export_posts_otlp_json_to_correct_url(monkeypatch):
    captured: dict = {}

    def fake_post(self, url, headers=None, content=None, **kw):
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = json.loads(content)
        req = httpx.Request("POST", url)
        return httpx.Response(200, request=req)

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    exp = TrueFoundryExporter(
        endpoint="https://my-org.truefoundry.cloud",
        api_key="abc",
        project="geminilens",
    )
    n = exp.export([_trace(), _trace()])
    assert n == 2
    assert captured["url"] == "https://my-org.truefoundry.cloud/api/otel/v1/traces"
    assert captured["headers"]["Authorization"] == "Bearer abc"
    assert "TFY-Tracing-Project" in captured["headers"]
    body = captured["body"]
    assert "resourceSpans" in body
    spans = body["resourceSpans"][0]["scopeSpans"][0]["spans"]
    assert len(spans) == 2


def test_export_empty_is_noop(monkeypatch):
    called = {"n": 0}

    def fake_post(self, *a, **kw):
        called["n"] += 1
        return httpx.Response(200, request=httpx.Request("POST", "http://x"))

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    exp = TrueFoundryExporter(endpoint="https://x.truefoundry.cloud", api_key="t")
    assert exp.export([]) == 0
    assert called["n"] == 0
