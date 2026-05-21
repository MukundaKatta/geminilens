"""Push GeminiLens traces to MongoDB Atlas as documents in a collection,
via the MongoDB Atlas Data API (HTTPS, no `pymongo` dep required).

Use cases this unlocks:

  * Drop GeminiLens trace JSONL into the same Atlas cluster that holds
    your agent's vector index, so you can do `$lookup` joins between
    "the question I asked" and "what the agent did with it".
  * Cost / latency rollups via the Aggregation Framework in Atlas
    Charts without needing a separate observability backend.
  * The Rapid Agent / MongoDB hackathon track.

Pattern: one document per Trace, inserted via `insertMany`.

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


class MongoDBAtlasExporter:
    """Posts traces to MongoDB Atlas via the Data API.

    Required env vars (or constructor args):
        MONGODB_DATA_API_URL  e.g. https://us-east-1.aws.data.mongodb-api.com/app/data-xxxxx/endpoint/data/v1
        MONGODB_API_KEY       Atlas Data API key
        MONGODB_DATA_SOURCE   Cluster / data source name (e.g. "Cluster0")
        MONGODB_DATABASE      Database name (default: "geminilens")
        MONGODB_COLLECTION    Collection name (default: "traces")
    """

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        data_source: str | None = None,
        database: str | None = None,
        collection: str | None = None,
        timeout: float = 5.0,
    ):
        self.url = (url or os.getenv("MONGODB_DATA_API_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("MONGODB_API_KEY", "")
        self.data_source = data_source or os.getenv("MONGODB_DATA_SOURCE", "")
        self.database = database or os.getenv("MONGODB_DATABASE", "geminilens")
        self.collection = collection or os.getenv("MONGODB_COLLECTION", "traces")
        self.timeout = timeout
        if not self.url or not self.api_key or not self.data_source:
            raise ValueError(
                "MongoDBAtlasExporter needs MONGODB_DATA_API_URL, MONGODB_API_KEY, "
                "and MONGODB_DATA_SOURCE (or explicit constructor args)."
            )

    def _doc(self, trace: Trace | dict) -> dict:
        t = trace.to_dict() if isinstance(trace, Trace) else trace
        return {
            "trace_id": t.get("trace_id"),
            "timestamp": _iso(t.get("started_at")),
            "model": t.get("model"),
            "system": "google.gemini",
            "input_tokens": int(t.get("input_tokens") or 0),
            "output_tokens": int(t.get("output_tokens") or 0),
            "cached_tokens": int(t.get("cached_tokens") or 0),
            "cost_usd": float(t.get("cost_usd") or 0.0),
            "latency_ms": float(t.get("latency_ms") or 0.0),
            "prompt": (t.get("prompt") or "")[:8000],
            "response": (t.get("response") or "")[:8000],
            "tool_calls": len(t.get("tool_calls") or []),
            "tool_call_names": [
                tc.get("name") for tc in (t.get("tool_calls") or []) if isinstance(tc, dict)
            ],
            "tags": t.get("tags") or {},
            "error": t.get("error"),
        }

    def export(self, traces: Iterable[Trace | dict]) -> int:
        docs = [self._doc(t) for t in traces]
        if not docs:
            return 0
        url = f"{self.url}/action/insertMany"
        headers = {
            "Content-Type": "application/json",
            "Access-Control-Request-Headers": "*",
            "api-key": self.api_key,
        }
        payload = {
            "dataSource": self.data_source,
            "database": self.database,
            "collection": self.collection,
            "documents": docs,
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, content=json.dumps(payload))
            resp.raise_for_status()
        return len(docs)

    def export_one(self, trace: Trace | dict) -> None:
        self.export([trace])
