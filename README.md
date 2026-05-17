# GeminiLens

Drop-in observability for Gemini agents. Wrap any Vertex AI Gemini call and
get traces, cost, latency, drift, and tool-call audit out of the box. Ships
with a Streamlit dashboard.

Open source under Apache 2.0.

## What it does

- **Traces every Gemini call**: prompt, response, token usage, latency.
- **Per-call cost in USD** for Gemini 2.5 Pro/Flash/Flash-Lite and 2.0 Flash,
  with cached-input pricing.
- **Drift signals**: rolling p95 latency, mean cost, and output-length vs a
  baseline window, so you notice when the agent gets slower, pricier, or more
  verbose without you changing anything.
- **Egress allowlist**: tool calls go through an `httpx` client that throws
  if the agent tries to reach a host outside your allowlist. Useful for
  research and data-extraction agents.
- **JSONL trace store** plus an in-memory ring buffer, so traces are durable
  and the dashboard is fast.

## Install

```bash
git clone https://github.com/MukundaKatta/geminilens
cd geminilens
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## 30-second demo (no GCP needed)

```bash
PYTHONPATH=src python examples/quickstart.py
```

This writes 120 synthetic traces to `~/.geminilens/traces.jsonl` and prints
a drift report. Then start the dashboard:

```bash
PYTHONPATH=src streamlit run app/dashboard.py
```

## Real Gemini call (Vertex AI)

```bash
export GOOGLE_CLOUD_PROJECT=your-project-id
gcloud auth application-default login
PYTHONPATH=src streamlit run app/dashboard.py
```

The dashboard's sidebar will call `gemini-2.5-flash` via Vertex AI and the
trace, cost, and latency will land in the table.

## Use as a library

```python
from geminilens import GeminiObserver, TraceStore, EgressGuard
from google import genai

observer = GeminiObserver(store=TraceStore("traces.jsonl"))
guard = EgressGuard(allow=["en.wikipedia.org", "arxiv.org"])
client = genai.Client(vertexai=True, project="my-proj", location="us-central1")

with observer.trace(model="gemini-2.5-pro", prompt="...", agent="researcher") as tr:
    # Tool calls go through the guard; egress to other hosts will raise.
    summary = observer.run_tool(
        tr, "wiki", lambda t: guard.client().get(f"https://en.wikipedia.org/wiki/{t}").text,
        "Vertex_AI",
    )
    response = client.models.generate_content(model="gemini-2.5-pro", contents="...")
    observer.record_response(tr, response)
```

## Tests

```bash
PYTHONPATH=src pytest -q
```

## Repo layout

```
src/geminilens/      core library
  observer.py        trace context manager + tool-call recorder
  cost.py            Gemini USD cost calculator
  drift.py           rolling-window drift report
  store.py           JSONL + in-memory trace store
  guard.py           egress allowlist (httpx transport)
  agent.py           reference ResearchAgent using all of the above
app/dashboard.py     Streamlit dashboard
examples/            runnable quickstart
tests/               pytest suite
```

## Why this exists

Most LLM observability tools are either Python SDKs that lock you into one
vendor's hosted backend or full APM platforms that ask for an agent. GeminiLens
is the smallest piece in between: a single file you can drop into a Gemini
project and get the four numbers that matter (cost, latency, drift, tool
audit) without leaving your machine. The dashboard is local Streamlit, the
data is JSONL, and the cost table lives in the repo so you can audit it.
