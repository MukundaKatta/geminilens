"""Push GeminiLens traces to Dynatrace's Log Ingestion API
(`/api/v2/logs/ingest`). One log event per trace, with custom attributes for
cost, latency, drift, and tool calls so they show up in Dynatrace Notebooks
and DQL queries."""

from __future__ import annotations

import json
import os
from typing import Iterable

import httpx

from geminilens.observer import Trace


class DynatraceExporter:
    """Posts traces to Dynatrace as structured log events.

    Required env vars (or constructor args):
        DT_ENV_URL   e.g. https://abc12345.live.dynatrace.com
        DT_API_TOKEN with scope `logs.ingest`
    """

    def __init__(
        self,
        env_url: str | None = None,
        api_token: str | None = None,
        service_name: str = "geminilens",
        timeout: float = 5.0,
    ):
        self.env_url = (env_url or os.getenv("DT_ENV_URL", "")).rstrip("/")
        self.api_token = api_token or os.getenv("DT_API_TOKEN", "")
        self.service_name = service_name
        self.timeout = timeout
        if not self.env_url or not self.api_token:
            raise ValueError(
                "DynatraceExporter needs DT_ENV_URL and DT_API_TOKEN "
                "(or explicit constructor args)."
            )

    def _payload(self, trace: Trace | dict) -> dict:
        t = trace.to_dict() if isinstance(trace, Trace) else trace
        return {
            "timestamp": int((t.get("ended_at") or t.get("started_at") or 0) * 1000),
            "content": f"gemini call: {t.get('prompt','')[:200]}",
            "log.source": "geminilens",
            "service.name": self.service_name,
            "model.name": t.get("model"),
            "gen_ai.usage.input_tokens": t.get("input_tokens", 0),
            "gen_ai.usage.output_tokens": t.get("output_tokens", 0),
            "gen_ai.usage.cached_tokens": t.get("cached_tokens", 0),
            "gen_ai.usage.cost_usd": t.get("cost_usd", 0.0),
            "duration.ms": t.get("latency_ms", 0),
            "trace.id": t.get("trace_id"),
            "tool_calls": len(t.get("tool_calls") or []),
            "error": t.get("error"),
            **{f"tag.{k}": v for k, v in (t.get("tags") or {}).items()},
        }

    def export(self, traces: Iterable[Trace | dict]) -> int:
        events = [self._payload(t) for t in traces]
        if not events:
            return 0
        url = f"{self.env_url}/api/v2/logs/ingest"
        headers = {
            "Authorization": f"Api-Token {self.api_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, content=json.dumps(events))
            resp.raise_for_status()
        return len(events)

    def export_one(self, trace: Trace | dict) -> None:
        self.export([trace])
