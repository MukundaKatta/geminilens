import json
import time

import httpx
import pytest

from geminilens.exporters.dynatrace import DynatraceExporter
from geminilens.observer import Trace


def _trace() -> Trace:
    return Trace(
        trace_id="abc123",
        model="gemini-2.5-flash",
        started_at=time.time(),
        ended_at=time.time() + 0.5,
        prompt="hi",
        response="hello",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.0001,
        latency_ms=523.4,
        tags={"agent": "research", "env": "prod"},
    )


def test_init_requires_credentials(monkeypatch):
    monkeypatch.delenv("DT_ENV_URL", raising=False)
    monkeypatch.delenv("DT_API_TOKEN", raising=False)
    with pytest.raises(ValueError):
        DynatraceExporter()


def test_payload_shape():
    exp = DynatraceExporter(env_url="https://x.live.dynatrace.com", api_token="t")
    body = exp._payload(_trace())
    assert body["gen_ai.usage.input_tokens"] == 100
    assert body["gen_ai.usage.output_tokens"] == 50
    assert body["model.name"] == "gemini-2.5-flash"
    assert body["duration.ms"] == 523.4
    assert body["tag.agent"] == "research"
    assert body["service.name"] == "geminilens"
    assert body["trace.id"] == "abc123"


def test_export_posts_to_correct_url(monkeypatch):
    captured: dict = {}

    def fake_post(self, url, headers=None, content=None, **kw):
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = json.loads(content)
        req = httpx.Request("POST", url)
        return httpx.Response(200, request=req)

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    exp = DynatraceExporter(env_url="https://x.live.dynatrace.com", api_token="abc")
    n = exp.export([_trace(), _trace()])
    assert n == 2
    assert captured["url"] == "https://x.live.dynatrace.com/api/v2/logs/ingest"
    assert captured["headers"]["Authorization"] == "Api-Token abc"
    assert len(captured["body"]) == 2
    assert captured["body"][0]["model.name"] == "gemini-2.5-flash"
