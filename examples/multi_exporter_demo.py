"""Fan out one GeminiLens trace into every backend at once.

The point: GeminiLens core gives you one Trace per Gemini call. Where you
send that Trace is a runtime decision. This demo shapes a single Trace
and fires it at five different exporters in parallel:

  * Arize Phoenix (OpenInference spans)
  * Splunk HEC (events)
  * Dynatrace Logs (events)
  * Elastic _bulk (ECS documents)
  * GitLab Observability (OTLP spans)
  * MongoDB Atlas Data API (documents)
  * TrueFoundry tracing (OTLP spans)
  * Local JSONL on disk

Run:

    python examples/multi_exporter_demo.py

With no env vars set, the demo runs against `httpx.MockTransport` fakes
of every backend, so it works offline. Set the right env vars
(`PHOENIX_ENDPOINT`, `SPLUNK_HEC_URL` + `SPLUNK_HEC_TOKEN`, etc.) and
the same code hits real endpoints.
"""

from __future__ import annotations

import os
import time
from typing import Iterable

import httpx

from geminilens.exporters import (
    ArizePhoenixExporter,
    DynatraceExporter,
    ElasticExporter,
    GitLabExporter,
    JsonlFileExporter,
    MongoDBAtlasExporter,
    SplunkHECExporter,
    TrueFoundryExporter,
)
from geminilens.observer import ToolCall, Trace


# ---- demo trace ------------------------------------------------------------


def make_demo_trace() -> Trace:
    return Trace(
        trace_id="demo-" + str(int(time.time())),
        model="gemini-2.5-flash",
        started_at=time.time(),
        ended_at=time.time() + 0.812,
        prompt="The user wants to know why /checkout returned 500s in the last hour.",
        response=(
            "I searched Splunk for the last hour of /checkout 500 errors. "
            "47 events. All trace back to the new payment provider deploy at 14:02."
        ),
        input_tokens=412,
        output_tokens=178,
        cached_tokens=380,  # mostly cached because the system prompt is stable
        cost_usd=0.000_18,
        latency_ms=812.0,
        tool_calls=[
            ToolCall(name="splunk_search", args={"spl": "index=app /checkout 500"},
                     result={"count": 47}, duration_ms=412.0),
            ToolCall(name="get_deploy_history", args={"service": "checkout"},
                     result={"latest": "14:02"}, duration_ms=121.0),
        ],
        tags={"agent": "sre-bot", "track": "splunk-agentic-ops"},
    )


# ---- offline fakes ---------------------------------------------------------


def _fake_handler(request: httpx.Request) -> httpx.Response:
    """Catch-all responder that returns 200 for every backend in the demo."""
    host = request.url.host
    path = request.url.path
    if "phoenix" in host or "phoenix" in path:
        return httpx.Response(200, json={"partialSuccess": {}})
    if "splunk" in host:
        return httpx.Response(200, json={"text": "Success", "code": 0})
    if "dynatrace" in host or "live.dynatrace" in host:
        return httpx.Response(200, json={})
    if "found.io" in host or path.endswith("_bulk"):
        return httpx.Response(
            200,
            json={"items": [{"index": {"status": 201, "_id": "x"}}], "errors": False},
        )
    if "gitlab" in host:
        return httpx.Response(200, json={})
    if "mongodb-api.com" in host:
        return httpx.Response(200, json={"insertedIds": ["a", "b"]})
    if "truefoundry" in host:
        return httpx.Response(200, json={})
    return httpx.Response(200, text="ok")


def _install_offline_transport():
    """Monkey-patch httpx.Client so every exporter posts into MockTransport."""
    import httpx as _httpx

    real_client_init = _httpx.Client.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = _httpx.MockTransport(_fake_handler)
        real_client_init(self, *args, **kwargs)

    _httpx.Client.__init__ = patched_init
    return real_client_init


# ---- demo loop -------------------------------------------------------------


def build_exporters() -> list:
    """Build every exporter we ship. Each uses dummy creds; the offline
    transport above absorbs the POSTs so nothing actually leaves the box."""
    return [
        ArizePhoenixExporter(endpoint="http://localhost:6006", project="demo"),
        SplunkHECExporter(url="https://splunk.example.com:8088", token="demo-token"),
        DynatraceExporter(env_url="https://abc.live.dynatrace.com", api_token="demo"),
        ElasticExporter(url="https://my-cluster.es.us-east-1.aws.found.io", api_key="demo"),
        GitLabExporter(url="https://gitlab.com", project_id="12345", token="demo-glpat"),
        MongoDBAtlasExporter(
            url="https://us-east-1.aws.data.mongodb-api.com/app/data-demo/endpoint/data/v1",
            api_key="demo",
            data_source="Cluster0",
        ),
        TrueFoundryExporter(endpoint="https://demo.truefoundry.cloud", api_key="demo"),
        JsonlFileExporter(path="runs/multi_exporter_demo.jsonl"),
    ]


def main() -> None:
    online = bool(os.environ.get("GEMINILENS_LIVE_EXPORTERS"))
    real_init = None
    if not online:
        real_init = _install_offline_transport()

    trace = make_demo_trace()
    os.makedirs("runs", exist_ok=True)

    exporters = build_exporters()
    print(f"Built {len(exporters)} exporters\n")
    print(f"Trace: {trace.trace_id}  model={trace.model}  "
          f"cost=${trace.cost_usd:.6f}  latency={trace.latency_ms:.0f}ms\n")

    for exp in exporters:
        name = type(exp).__name__
        try:
            n = exp.export([trace])
            print(f"  [ok] {name:<22}  exported {n}")
        except Exception as e:
            print(f"  [!!] {name:<22}  {e}")

    print(f"\nAlso wrote local JSONL: runs/multi_exporter_demo.jsonl")
    print(f"\nMode: {'LIVE' if online else 'OFFLINE (MockTransport)'}")

    if real_init is not None:
        import httpx as _httpx
        _httpx.Client.__init__ = real_init  # restore


if __name__ == "__main__":
    main()
