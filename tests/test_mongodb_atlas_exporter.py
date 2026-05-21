import json

import httpx
import pytest

from geminilens.exporters.mongodb_atlas import MongoDBAtlasExporter
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


def test_init_requires_credentials(monkeypatch):
    monkeypatch.delenv("MONGODB_DATA_API_URL", raising=False)
    monkeypatch.delenv("MONGODB_API_KEY", raising=False)
    monkeypatch.delenv("MONGODB_DATA_SOURCE", raising=False)
    with pytest.raises(ValueError):
        MongoDBAtlasExporter()


def test_doc_carries_genai_fields():
    exp = MongoDBAtlasExporter(
        url="https://data.mongodb-api.com/app/abc/endpoint/data/v1",
        api_key="k",
        data_source="Cluster0",
    )
    d = exp._doc(_trace())
    assert d["trace_id"] == "abc123"
    assert d["model"] == "gemini-2.5-flash"
    assert d["system"] == "google.gemini"
    assert d["input_tokens"] == 100
    assert d["output_tokens"] == 50
    assert d["cached_tokens"] == 10
    assert d["cost_usd"] == pytest.approx(0.0001)
    assert d["timestamp"].endswith("+00:00")
    assert d["tags"]["agent"] == "research"


def test_export_posts_insertMany_with_apikey_header(monkeypatch):
    captured: dict = {}

    def fake_post(self, url, headers=None, content=None, **kw):
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = json.loads(content)
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    exp = MongoDBAtlasExporter(
        url="https://us-east-1.aws.data.mongodb-api.com/app/data-xyz/endpoint/data/v1",
        api_key="atlas-key",
        data_source="Cluster0",
        database="ai_observability",
        collection="gemini_runs",
    )
    n = exp.export([_trace(), _trace(), _trace()])
    assert n == 3
    assert captured["url"] == (
        "https://us-east-1.aws.data.mongodb-api.com/app/data-xyz/endpoint/data/v1/action/insertMany"
    )
    assert captured["headers"]["api-key"] == "atlas-key"
    body = captured["body"]
    assert body["dataSource"] == "Cluster0"
    assert body["database"] == "ai_observability"
    assert body["collection"] == "gemini_runs"
    assert len(body["documents"]) == 3
    assert body["documents"][0]["model"] == "gemini-2.5-flash"


def test_export_empty_is_noop(monkeypatch):
    called = {"n": 0}

    def fake_post(self, *a, **kw):
        called["n"] += 1
        return httpx.Response(200, request=httpx.Request("POST", "http://x"))

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    exp = MongoDBAtlasExporter(
        url="https://x.mongodb-api.com/app/data-xyz/endpoint/data/v1",
        api_key="k",
        data_source="Cluster0",
    )
    assert exp.export([]) == 0
    assert called["n"] == 0
