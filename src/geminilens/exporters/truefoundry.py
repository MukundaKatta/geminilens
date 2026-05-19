"""Push GeminiLens traces to TrueFoundry's AI Gateway tracing endpoint as
OTLP-JSON spans (`/api/otel/v1/traces`).

TrueFoundry's gateway accepts standard OpenTelemetry OTLP/HTTP. This exporter
shapes a Trace into a single CLIENT span with Gen-AI semconv attributes
(`gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`,
`gen_ai.usage.cost_usd`) plus GeminiLens extras (drift, tool_calls).

No SDK dependency — just one POST per batch."""

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


class TrueFoundryExporter:
    """Posts traces to TrueFoundry as OTLP/HTTP-JSON spans.

    Required env vars (or constructor args):
        TFY_ENDPOINT       e.g. https://your-org.truefoundry.cloud
        TFY_API_KEY        TrueFoundry API key with tracing scope
        TFY_PROJECT        Optional. e.g. "geminilens" — shapes the
                           TFY-Tracing-Project header.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        project: str | None = None,
        service_name: str = "geminilens",
        timeout: float = 5.0,
    ):
        self.endpoint = (endpoint or os.getenv("TFY_ENDPOINT", "")).rstrip("/")
        self.api_key = api_key or os.getenv("TFY_API_KEY", "")
        self.project = project or os.getenv("TFY_PROJECT", "")
        self.service_name = service_name
        self.timeout = timeout
        if not self.endpoint or not self.api_key:
            raise ValueError(
                "TrueFoundryExporter needs TFY_ENDPOINT and TFY_API_KEY "
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
        url = f"{self.endpoint}/api/otel/v1/traces"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.project:
            headers["TFY-Tracing-Project"] = (
                f"tracing-project:truefoundry/{self.project}/{self.service_name}"
            )
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, content=json.dumps(self._payload(spans)))
            resp.raise_for_status()
        return len(spans)

    def export_one(self, trace: Trace | dict) -> None:
        self.export([trace])
