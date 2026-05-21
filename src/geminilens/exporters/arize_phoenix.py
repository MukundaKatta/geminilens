"""Push GeminiLens traces to Arize Phoenix as OpenInference-spec spans
(`/v1/traces`, OTLP/HTTP-JSON).

Phoenix is the open-source Arize tracing backend. It accepts standard OTLP
spans on its OTel endpoint, but renders the LLM-specific fields nicely when
you stamp them using the **OpenInference** semantic conventions
(`llm.model_name`, `llm.token_count.prompt`, `llm.token_count.completion`,
`openinference.span.kind=LLM`, etc.).

This exporter shapes a GeminiLens `Trace` into a single span tagged with both:

  * OpenTelemetry Gen-AI semconv (`gen_ai.*`) so it travels through any
    generic OTel pipeline
  * OpenInference attrs (`llm.*`, `openinference.span.kind`) so Phoenix's UI
    treats it as an LLM span and the eval/dataset workflows pick it up

No SDK dep. Just an httpx POST per batch."""

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


class ArizePhoenixExporter:
    """Posts traces to Arize Phoenix as OpenInference-shaped OTLP spans.

    Phoenix accepts spans on `<endpoint>/v1/traces` (OTLP/HTTP-JSON).
    For Arize Cloud, set `PHOENIX_API_KEY` and the standard cloud endpoint
    (`https://app.phoenix.arize.com`). For self-hosted Phoenix, set
    `PHOENIX_ENDPOINT=http://localhost:6006` and leave the key empty.

    Required env vars (or constructor args):
        PHOENIX_ENDPOINT  e.g. http://localhost:6006 or https://app.phoenix.arize.com
        PHOENIX_API_KEY   Optional. Required for Arize Cloud; empty for local.
        PHOENIX_PROJECT   Optional. Project name; sets the
                          `openinference.project.name` resource attribute.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        project: str | None = None,
        service_name: str = "geminilens",
        timeout: float = 5.0,
    ):
        self.endpoint = (endpoint or os.getenv("PHOENIX_ENDPOINT", "")).rstrip("/")
        self.api_key = api_key or os.getenv("PHOENIX_API_KEY", "")
        self.project = project or os.getenv("PHOENIX_PROJECT", "geminilens")
        self.service_name = service_name
        self.timeout = timeout
        if not self.endpoint:
            raise ValueError(
                "ArizePhoenixExporter needs PHOENIX_ENDPOINT "
                "(e.g. http://localhost:6006 or https://app.phoenix.arize.com)."
            )

    def _span(self, trace: Trace | dict) -> dict:
        t = trace.to_dict() if isinstance(trace, Trace) else trace
        trace_id_hex = (t.get("trace_id") or "").replace("-", "")[:32].ljust(32, "0")
        span_id_hex = trace_id_hex[:16]
        start_ns = int((t.get("started_at") or 0) * 1_000_000_000)
        end_ns = int((t.get("ended_at") or t.get("started_at") or 0) * 1_000_000_000)
        model = t.get("model") or ""
        prompt = (t.get("prompt") or "")[:8000]
        completion = (t.get("response") or "")[:8000]
        attrs = [
            # OpenInference (Phoenix renders nicely)
            _attr("openinference.span.kind", "LLM"),
            _attr("llm.model_name", model),
            _attr("llm.system", "google.gemini"),
            _attr("llm.token_count.prompt", int(t.get("input_tokens") or 0)),
            _attr("llm.token_count.completion", int(t.get("output_tokens") or 0)),
            _attr("llm.token_count.total",
                  int(t.get("input_tokens") or 0) + int(t.get("output_tokens") or 0)),
            _attr("llm.token_count.prompt.cache_read",
                  int(t.get("cached_tokens") or 0)),
            _attr("input.value", prompt),
            _attr("output.value", completion),
            # Generic Gen-AI semconv (other OTel pipelines)
            _attr("gen_ai.system", "google.gemini"),
            _attr("gen_ai.request.model", model),
            _attr("gen_ai.usage.input_tokens", int(t.get("input_tokens") or 0)),
            _attr("gen_ai.usage.output_tokens", int(t.get("output_tokens") or 0)),
            _attr("gen_ai.usage.cached_tokens", int(t.get("cached_tokens") or 0)),
            _attr("gen_ai.usage.cost_usd", float(t.get("cost_usd") or 0.0)),
            # GeminiLens extras
            _attr("gemini_lens.tool_calls", len(t.get("tool_calls") or [])),
            _attr("gemini_lens.latency_ms", float(t.get("latency_ms") or 0.0)),
        ]
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
                            _attr("openinference.project.name", self.project),
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
        url = f"{self.endpoint}/v1/traces"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.project:
            # Phoenix routes spans into projects via this header
            headers["x-phoenix-project-name"] = self.project
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, content=json.dumps(self._payload(spans)))
            resp.raise_for_status()
        return len(spans)

    def export_one(self, trace: Trace | dict) -> None:
        self.export([trace])
