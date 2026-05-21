"""Push GeminiLens traces to Splunk via the HTTP Event Collector
(`/services/collector/event`).

Splunk HEC accepts one JSON event per request body (or newline-delimited JSON
for batches). This exporter ships one event per GeminiLens `Trace`, stamped
with both Gen-AI semconv fields and Splunk-friendly indexed fields so the
events are queryable from Splunk Search and AI Assistant.

Use case for the Splunk Agentic Ops Hackathon: agents that call the
Splunk MCP Server and need their *own* run telemetry to land back in
Splunk for SREs to query alongside system data.

No SDK dep."""

from __future__ import annotations

import json
import os
from typing import Iterable

import httpx

from geminilens.observer import Trace


class SplunkHECExporter:
    """Posts traces to Splunk HEC as structured events.

    Required env vars (or constructor args):
        SPLUNK_HEC_URL    e.g. https://splunk.example.com:8088
        SPLUNK_HEC_TOKEN  A valid HEC token with index-write permission
        SPLUNK_INDEX      Optional. Splunk index name (default: "main")
        SPLUNK_SOURCETYPE Optional. Default: "geminilens:trace"
        SPLUNK_SOURCE     Optional. Default: "geminilens"
    """

    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
        index: str | None = None,
        sourcetype: str | None = None,
        source: str | None = None,
        verify_tls: bool = True,
        timeout: float = 5.0,
    ):
        self.url = (url or os.getenv("SPLUNK_HEC_URL", "")).rstrip("/")
        self.token = token or os.getenv("SPLUNK_HEC_TOKEN", "")
        self.index = index or os.getenv("SPLUNK_INDEX", "main")
        self.sourcetype = sourcetype or os.getenv("SPLUNK_SOURCETYPE", "geminilens:trace")
        self.source = source or os.getenv("SPLUNK_SOURCE", "geminilens")
        self.verify_tls = verify_tls
        self.timeout = timeout
        if not self.url or not self.token:
            raise ValueError(
                "SplunkHECExporter needs SPLUNK_HEC_URL and SPLUNK_HEC_TOKEN "
                "(or explicit constructor args)."
            )

    def _event(self, trace: Trace | dict) -> dict:
        t = trace.to_dict() if isinstance(trace, Trace) else trace
        # Splunk HEC envelope. `time` is unix seconds (float). Custom fields go
        # under `event` and are indexed if you've set up index-time field
        # extraction (recommended for hot queries on cost/latency).
        return {
            "time": t.get("started_at") or 0.0,
            "host": self.source,
            "source": self.source,
            "sourcetype": self.sourcetype,
            "index": self.index,
            "event": {
                "trace_id": t.get("trace_id"),
                "model": t.get("model"),
                "system": "google.gemini",
                "input_tokens": int(t.get("input_tokens") or 0),
                "output_tokens": int(t.get("output_tokens") or 0),
                "cached_tokens": int(t.get("cached_tokens") or 0),
                "cost_usd": float(t.get("cost_usd") or 0.0),
                "latency_ms": float(t.get("latency_ms") or 0.0),
                "tool_calls": len(t.get("tool_calls") or []),
                "error": t.get("error"),
                "prompt": (t.get("prompt") or "")[:2000],
                "completion": (t.get("response") or "")[:2000],
                "tags": t.get("tags") or {},
                "tool_call_names": [
                    tc.get("name") for tc in (t.get("tool_calls") or []) if isinstance(tc, dict)
                ],
            },
        }

    def export(self, traces: Iterable[Trace | dict]) -> int:
        events = [self._event(t) for t in traces]
        if not events:
            return 0
        # Splunk HEC supports concatenated JSON objects (no commas, no array)
        # in a single POST body. Newlines between events are optional but
        # make tcpdump-style debugging easier.
        body = "\n".join(json.dumps(e) for e in events)
        url = f"{self.url}/services/collector/event"
        headers = {
            "Authorization": f"Splunk {self.token}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.timeout, verify=self.verify_tls) as client:
            resp = client.post(url, headers=headers, content=body)
            resp.raise_for_status()
        return len(events)

    def export_one(self, trace: Trace | dict) -> None:
        self.export([trace])
