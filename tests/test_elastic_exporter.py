import base64
import json

import httpx
import pytest

from geminilens.exporters.elastic import ElasticExporter
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
        tags={"agent": "research"},
    )


def test_init_requires_auth(monkeypatch):
    monkeypatch.delenv("ELASTIC_URL", raising=False)
    monkeypatch.delenv("ELASTIC_API_KEY", raising=False)
    monkeypatch.delenv("ELASTIC_USERNAME", raising=False)
    monkeypatch.delenv("ELASTIC_PASSWORD", raising=False)
    with pytest.raises(ValueError):
        ElasticExporter()


def test_doc_uses_ecs_field_names():
    exp = ElasticExporter(url="https://es.example.com", api_key="k")
    doc = exp._doc(_trace())
    assert doc["@timestamp"].endswith("+00:00")
    assert doc["service.name"] == "geminilens"
    assert doc["event.dataset"] == "geminilens.trace"
    assert doc["event.kind"] == "event"
    assert doc["event.outcome"] == "success"
    assert doc["event.duration"] == 523_400_000  # ns
    assert doc["gen_ai.system"] == "google.gemini"
    assert doc["gen_ai.request.model"] == "gemini-2.5-flash"
    assert doc["gen_ai.usage.input_tokens"] == 100
    assert doc["geminilens.tool_calls"] == 0
    assert doc["labels.agent"] == "research"


def test_doc_marks_failure_on_error():
    exp = ElasticExporter(url="https://es.example.com", api_key="k")
    tr = _trace()
    tr.error = "Vertex AI 429"
    doc = exp._doc(tr)
    assert doc["error.message"] == "Vertex AI 429"
    assert doc["event.outcome"] == "failure"


def test_export_posts_to_bulk_endpoint_with_apikey(monkeypatch):
    captured: dict = {}

    def fake_post(self, url, headers=None, content=None, **kw):
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = content
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    exp = ElasticExporter(
        url="https://my-cluster.es.us-east-1.aws.found.io",
        api_key="abc",
        index="agents-traces",
    )
    n = exp.export([_trace(), _trace()])
    assert n == 2
    assert captured["url"] == "https://my-cluster.es.us-east-1.aws.found.io/_bulk"
    assert captured["headers"]["Authorization"] == "ApiKey abc"
    assert captured["headers"]["Content-Type"] == "application/x-ndjson"
    lines = [ln for ln in captured["body"].split("\n") if ln.strip()]
    # action line + doc line per trace = 4 lines for 2 traces
    assert len(lines) == 4
    action = json.loads(lines[0])
    assert action == {"index": {"_index": "agents-traces"}}
    doc = json.loads(lines[1])
    assert doc["service.name"] == "geminilens"


def test_export_supports_basic_auth(monkeypatch):
    captured: dict = {}

    def fake_post(self, url, headers=None, content=None, **kw):
        captured["headers"] = headers
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    exp = ElasticExporter(
        url="https://es.example.com",
        username="elastic",
        password="changeme",
    )
    exp.export([_trace()])
    expected = "Basic " + base64.b64encode(b"elastic:changeme").decode()
    assert captured["headers"]["Authorization"] == expected


def test_export_empty_is_noop(monkeypatch):
    called = {"n": 0}

    def fake_post(self, *a, **kw):
        called["n"] += 1
        return httpx.Response(200, request=httpx.Request("POST", "http://x"))

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    exp = ElasticExporter(url="https://es.example.com", api_key="k")
    assert exp.export([]) == 0
    assert called["n"] == 0
