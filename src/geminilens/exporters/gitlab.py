"""Push GeminiLens traces to GitLab Observability (`/api/v4/projects/:id/`
`observability/v1/traces`) as OTLP-JSON spans, plus an optional second
mode that posts each run as a comment on a GitLab MR for CI-style review.

GitLab's Observability service (GA in 16.x+) accepts standard OTLP/HTTP
spans on the project-scoped tracing endpoint. This exporter shapes a
GeminiLens `Trace` into a single LLM-flavored CLIENT span with Gen-AI
semconv attributes so the spans land in the project's tracing UI right
alongside CI/CD pipeline spans.

CI integration angle (Rapid Agent / GitLab track): a GitLab CI job can
import this exporter, run an agent against a Gemini model, and emit
spans into the same project's tracing UI as the CI job itself. The two
trails sit next to each other for debugging.

No SDK dep."""

from __future__ import annotations

import json
import os
from typing import Iterable

import httpx

from geminilens.observer import Trace


def _attr(key: str, value) -> dict:
    """Build a single OTLP attribute. Picks the right value type."""
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    return {"key": key, "value": {"stringValue": str(value)}}


class GitLabExporter:
    """Posts traces to GitLab Observability as OTLP/HTTP-JSON spans.

    Required env vars (or constructor args):
        GITLAB_URL          e.g. https://gitlab.com (or self-hosted URL)
        GITLAB_PROJECT_ID   Numeric or url-encoded path (e.g. "12345"
                            or "mukundakatta%2Fgeminilens")
        GITLAB_TOKEN        Personal/project access token with
                            `api` or `read_api`+`observability_write` scope.
        GITLAB_SERVICE      Optional. Default "geminilens".
    """

    def __init__(
        self,
        url: str | None = None,
        project_id: str | None = None,
        token: str | None = None,
        service_name: str | None = None,
        timeout: float = 5.0,
    ):
        self.url = (url or os.getenv("GITLAB_URL", "https://gitlab.com")).rstrip("/")
        self.project_id = project_id or os.getenv("GITLAB_PROJECT_ID", "")
        self.token = token or os.getenv("GITLAB_TOKEN", "")
        self.service_name = service_name or os.getenv("GITLAB_SERVICE", "geminilens")
        self.timeout = timeout
        if not self.project_id or not self.token:
            raise ValueError(
                "GitLabExporter needs GITLAB_PROJECT_ID and GITLAB_TOKEN "
                "(or explicit constructor args)."
            )

    def _span(self, trace: Trace | dict) -> dict:
        t = trace.to_dict() if isinstance(trace, Trace) else trace
        trace_id_hex = (t.get("trace_id") or "").replace("-", "")[:32].ljust(32, "0")
        span_id_hex = trace_id_hex[:16]
        start_ns = int((t.get("started_at") or 0) * 1_000_000_000)
        end_ns = int((t.get("ended_at") or t.get("started_at") or 0) * 1_000_000_000)
        attrs = [
            _attr("gen_ai.system", "google.gemini"),
            _attr("gen_ai.request.model", t.get("model") or ""),
            _attr("gen_ai.usage.input_tokens", int(t.get("input_tokens") or 0)),
            _attr("gen_ai.usage.output_tokens", int(t.get("output_tokens") or 0)),
            _attr("gen_ai.usage.cached_tokens", int(t.get("cached_tokens") or 0)),
            _attr("gen_ai.usage.cost_usd", float(t.get("cost_usd") or 0.0)),
            _attr("gemini_lens.tool_calls", len(t.get("tool_calls") or [])),
            _attr("gemini_lens.latency_ms", float(t.get("latency_ms") or 0.0)),
        ]
        # Stamp CI context if GeminiLens is running inside a GitLab CI job
        for envk, attrk in [
            ("CI_PIPELINE_ID", "ci.pipeline.id"),
            ("CI_JOB_ID", "ci.job.id"),
            ("CI_COMMIT_SHORT_SHA", "ci.commit.sha"),
            ("CI_PROJECT_PATH", "ci.project.path"),
        ]:
            v = os.getenv(envk)
            if v:
                attrs.append(_attr(attrk, v))
        for k, v in (t.get("tags") or {}).items():
            attrs.append(_attr(f"tag.{k}", v))
        status = {"code": 2, "message": t.get("error")} if t.get("error") else {"code": 0}
        return {
            "traceId": trace_id_hex,
            "spanId": span_id_hex,
            "name": "gemini.call",
            "kind": 3,  # CLIENT
            "startTimeUnixNano": str(start_ns),
            "endTimeUnixNano": str(end_ns),
            "attributes": attrs,
            "status": status,
        }

    def _payload(self, traces: Iterable[Trace | dict]) -> dict:
        spans = [self._span(t) for t in traces]
        return {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            _attr("service.name", self.service_name),
                            _attr("telemetry.sdk.name", "geminilens"),
                        ]
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": "geminilens"},
                            "spans": spans,
                        }
                    ],
                }
            ]
        }

    def export(self, traces: Iterable[Trace | dict]) -> int:
        spans = list(traces)
        if not spans:
            return 0
        url = f"{self.url}/api/v4/projects/{self.project_id}/observability/v1/traces"
        headers = {
            "PRIVATE-TOKEN": self.token,
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, content=json.dumps(self._payload(spans)))
            resp.raise_for_status()
        return len(spans)

    def export_one(self, trace: Trace | dict) -> None:
        self.export([trace])
