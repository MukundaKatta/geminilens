"""Push GeminiLens traces to Elasticsearch via the `_bulk` endpoint, using
Elastic Common Schema (ECS) field names so Kibana renders the events
natively in the Discover and Logs UIs.

ECS conventions we follow:

  * `@timestamp` (ISO-8601)
  * `service.name`, `service.version`
  * `event.dataset = "geminilens.trace"`, `event.kind = "event"`
  * `error.message` for failed runs

We also keep the standard Gen-AI semconv fields under `gen_ai.*` so the
same index can be queried by any OTel-aware downstream.

No SDK dep. Just one POST per batch."""

from __future__ import annotations

import datetime as _dt
import json
import os
from typing import Iterable

import httpx

from geminilens.observer import Trace


def _iso(ts: float | None) -> str:
    if not ts:
        return _dt.datetime.now(tz=_dt.timezone.utc).isoformat()
    return _dt.datetime.fromtimestamp(ts, tz=_dt.timezone.utc).isoformat()


class ElasticExporter:
    """Posts traces to Elasticsearch as ECS-shaped documents.

    Required env vars (or constructor args):
        ELASTIC_URL    e.g. https://my-cluster.es.us-east-1.aws.found.io
        ELASTIC_API_KEY  An API key with index write permission, OR set
                         ELASTIC_USERNAME + ELASTIC_PASSWORD for basic auth.
        ELASTIC_INDEX  Optional, default "geminilens-traces"
    """

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        username: str | None = None,
        password: str | None = None,
        index: str | None = None,
        service_name: str = "geminilens",
        timeout: float = 5.0,
    ):
        self.url = (url or os.getenv("ELASTIC_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("ELASTIC_API_KEY", "")
        self.username = username or os.getenv("ELASTIC_USERNAME", "")
        self.password = password or os.getenv("ELASTIC_PASSWORD", "")
        self.index = index or os.getenv("ELASTIC_INDEX", "geminilens-traces")
        self.service_name = service_name
        self.timeout = timeout
        if not self.url or not (self.api_key or (self.username and self.password)):
            raise ValueError(
                "ElasticExporter needs ELASTIC_URL plus either ELASTIC_API_KEY "
                "or (ELASTIC_USERNAME + ELASTIC_PASSWORD)."
            )

    def _doc(self, trace: Trace | dict) -> dict:
        t = trace.to_dict() if isinstance(trace, Trace) else trace
        doc = {
            "@timestamp": _iso(t.get("started_at")),
            "service.name": self.service_name,
            "service.version": "geminilens",
            "event.dataset": "geminilens.trace",
            "event.kind": "event",
            "event.duration": int((t.get("latency_ms") or 0) * 1_000_000),  # nanoseconds, ECS
            "trace.id": t.get("trace_id"),
            # Gen-AI semconv (OTel)
            "gen_ai.system": "google.gemini",
            "gen_ai.request.model": t.get("model"),
            "gen_ai.usage.input_tokens": int(t.get("input_tokens") or 0),
            "gen_ai.usage.output_tokens": int(t.get("output_tokens") or 0),
            "gen_ai.usage.cached_tokens": int(t.get("cached_tokens") or 0),
            "gen_ai.usage.cost_usd": float(t.get("cost_usd") or 0.0),
            # GeminiLens extras (queryable)
            "geminilens.prompt": (t.get("prompt") or "")[:8000],
            "geminilens.response": (t.get("response") or "")[:8000],
            "geminilens.tool_calls": len(t.get("tool_calls") or []),
            "geminilens.tool_call_names": [
                tc.get("name") for tc in (t.get("tool_calls") or []) if isinstance(tc, dict)
            ],
            "geminilens.latency_ms": float(t.get("latency_ms") or 0.0),
        }
        for k, v in (t.get("tags") or {}).items():
            doc[f"labels.{k}"] = v
        if t.get("error"):
            doc["error.message"] = t["error"]
            doc["event.outcome"] = "failure"
        else:
            doc["event.outcome"] = "success"
        return doc

    def _bulk_body(self, traces: Iterable[Trace | dict]) -> str:
        """Build the NDJSON body for Elasticsearch's _bulk endpoint:
        alternating action lines and document lines."""
        lines: list[str] = []
        for t in traces:
            lines.append(json.dumps({"index": {"_index": self.index}}))
            lines.append(json.dumps(self._doc(t)))
        return "\n".join(lines) + "\n"

    def _auth_header(self) -> dict[str, str]:
        if self.api_key:
            return {"Authorization": f"ApiKey {self.api_key}"}
        import base64
        token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    def export(self, traces: Iterable[Trace | dict]) -> int:
        traces_list = list(traces)
        if not traces_list:
            return 0
        body = self._bulk_body(traces_list)
        url = f"{self.url}/_bulk"
        headers = {"Content-Type": "application/x-ndjson", **self._auth_header()}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, content=body)
            resp.raise_for_status()
        return len(traces_list)

    def export_one(self, trace: Trace | dict) -> None:
        self.export([trace])
