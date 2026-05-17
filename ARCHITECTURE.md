# Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│                       Your agent code                             │
│                                                                   │
│   with observer.trace(model, prompt) as tr:                       │
│       data = observer.run_tool(tr, "wiki", fetch, topic)          │
│       resp = client.models.generate_content(...)                  │
│       observer.record_response(tr, resp)                          │
└────────────────┬──────────────────────────────┬───────────────────┘
                 │                              │
                 ▼                              ▼
       ┌──────────────────┐         ┌────────────────────────┐
       │  EgressGuard     │         │  GeminiObserver        │
       │  httpx transport │         │  trace context manager │
       │  allowlist       │         │  cost + latency + tags │
       └─────┬────────────┘         └──────────┬─────────────┘
             │ allowed only                    │
             ▼                                 ▼
    ┌────────────────────┐         ┌─────────────────────────────┐
    │  External APIs     │         │  TraceStore                 │
    │  (wikipedia, etc.) │         │  in-mem ring + JSONL append │
    └────────────────────┘         └──────────────┬──────────────┘
                                                  │
                                                  ▼
              ┌──────────────────────┐    ┌─────────────────────┐
              │  Streamlit dashboard │    │  compute_drift()    │
              │  metrics + charts    │◄───┤  rolling vs base    │
              └──────────────────────┘    └─────────────────────┘
                       ▲
                       │
                       │   queried by user
              ┌────────┴────────┐
              │  Vertex AI      │
              │  Gemini 2.5 *   │
              └─────────────────┘
```

## Components

### `observer.GeminiObserver`
Context manager (`observer.trace(...)`) that opens a `Trace` record, captures
prompt and tags, then on exit fills in latency, computes USD cost via
`cost.gemini_cost`, and appends to the store. Exceptions inside the block are
captured on `Trace.error` and re-raised; the trace is still flushed.

Token counts and response text are extracted from a google-genai response via
`record_response(trace, response)`, which reads `usage_metadata` fields
defined by the Gemini API.

Tool calls go through `run_tool(trace, name, fn, *args)` which times the call,
captures `args`, `result`, and any error, and attaches a `ToolCall` to the
trace.

### `cost.gemini_cost`
Pure-Python tiered pricing for Gemini 2.5 Pro, 2.5 Flash, 2.5 Flash-Lite,
2.0 Flash, 2.0 Flash-Lite. Returns a `CostBreakdown` dataclass. Cached input
priced at 25 percent of standard input. Sourced from
[ai.google.dev/gemini-api/docs/pricing](https://ai.google.dev/gemini-api/docs/pricing).

### `drift.compute_drift`
Splits the trace history into a rolling window (default 20 traces) and a
baseline window (default 80 traces preceding the rolling). Reports the ratio
of rolling p95 latency to baseline p95 latency, rolling mean cost to baseline
mean cost, and rolling mean output tokens to baseline mean. Values above 1
mean the agent is getting worse on that dimension.

### `store.TraceStore`
Two-tier store. In-memory `deque` capped at 5000 entries for the dashboard,
and a JSONL append-only file at `~/.geminilens/traces.jsonl` (or any path you
choose) for durability and offline analysis.

### `guard.EgressGuard`
Custom `httpx.HTTPTransport` that checks the request URL against an allowlist
of hostnames. Exact match and subdomain match supported. Raises `EgressBlocked`
on violation; the violation URL is also recorded for the audit log.

### `agent.ResearchAgent`
Reference Gemini agent that takes a question, optionally fetches a Wikipedia
summary through the egress-guarded client, and asks Gemini for an answer.
Falls back to a deterministic offline response when GCP credentials are not
configured, so the dashboard demo still works without a project.

### `app/dashboard.py`
Streamlit single-page app. Sidebar lets you fire an agent call or seed
synthetic traces. Main view shows top-line metrics, a drift report, latency
and cost timelines, and the last 50 traces in a table.

## Data flow on a single agent call

1. User types a question in the dashboard.
2. `ResearchAgent.answer(question)` opens `observer.trace(...)`.
3. If `use_tool` is on, the agent calls `_fetch_wiki_summary` through
   `EgressGuard.client()`. Only hosts on the allowlist pass.
4. The Gemini call goes to Vertex AI in the configured project.
5. `record_response` pulls token counts from `usage_metadata` and the
   response text.
6. The context manager exit fills in latency, computes cost, appends to the
   `TraceStore`.
7. The dashboard re-reads the store and rerenders.

## What is intentionally not in scope (v0.1)

- Distributed tracing across multiple processes (single process only).
- Multi-tenant auth on the dashboard (assumed local-only).
- Streaming-response tokenization (final response only).
- Vector-store drift (the libs exist separately; not wired here).
