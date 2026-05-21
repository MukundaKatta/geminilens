import json

import httpx
import pytest

from geminilens.exporters.gitlab import GitLabExporter
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
        tags={"agent": "ci"},
    )


def _find_attr(attrs, key):
    for a in attrs:
        if a["key"] == key:
            return a["value"]
    return None


def test_init_requires_project_and_token(monkeypatch):
    monkeypatch.delenv("GITLAB_PROJECT_ID", raising=False)
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    with pytest.raises(ValueError):
        GitLabExporter()


def test_span_carries_genai_semconv():
    exp = GitLabExporter(project_id="12345", token="t")
    span = exp._span(_trace())
    attrs = span["attributes"]
    assert _find_attr(attrs, "gen_ai.system")["stringValue"] == "google.gemini"
    assert _find_attr(attrs, "gen_ai.usage.input_tokens")["intValue"] == "100"
    assert _find_attr(attrs, "gen_ai.usage.cost_usd")["doubleValue"] == pytest.approx(0.0001)
    assert _find_attr(attrs, "tag.agent")["stringValue"] == "ci"


def test_span_stamps_gitlab_ci_env_vars_when_present(monkeypatch):
    monkeypatch.setenv("CI_PIPELINE_ID", "55555")
    monkeypatch.setenv("CI_JOB_ID", "98765")
    monkeypatch.setenv("CI_COMMIT_SHORT_SHA", "deadbeef")
    monkeypatch.setenv("CI_PROJECT_PATH", "mukundakatta/geminilens")

    exp = GitLabExporter(project_id="12345", token="t")
    span = exp._span(_trace())
    attrs = span["attributes"]
    assert _find_attr(attrs, "ci.pipeline.id")["stringValue"] == "55555"
    assert _find_attr(attrs, "ci.job.id")["stringValue"] == "98765"
    assert _find_attr(attrs, "ci.commit.sha")["stringValue"] == "deadbeef"
    assert _find_attr(attrs, "ci.project.path")["stringValue"] == "mukundakatta/geminilens"


def test_export_posts_otlp_to_observability_endpoint(monkeypatch):
    captured: dict = {}

    def fake_post(self, url, headers=None, content=None, **kw):
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = json.loads(content)
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    exp = GitLabExporter(
        url="https://gitlab.com",
        project_id="12345",
        token="glpat-xxxxx",
    )
    n = exp.export([_trace(), _trace()])
    assert n == 2
    assert captured["url"] == (
        "https://gitlab.com/api/v4/projects/12345/observability/v1/traces"
    )
    assert captured["headers"]["PRIVATE-TOKEN"] == "glpat-xxxxx"
    spans = captured["body"]["resourceSpans"][0]["scopeSpans"][0]["spans"]
    assert len(spans) == 2


def test_export_empty_is_noop(monkeypatch):
    called = {"n": 0}

    def fake_post(self, *a, **kw):
        called["n"] += 1
        return httpx.Response(200, request=httpx.Request("POST", "http://x"))

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    exp = GitLabExporter(project_id="12345", token="t")
    assert exp.export([]) == 0
    assert called["n"] == 0
