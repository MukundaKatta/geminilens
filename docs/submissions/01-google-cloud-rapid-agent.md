# Google Cloud Rapid Agent Hackathon (Dynatrace track)

Devpost: https://rapid-agent.devpost.com
Deadline: 2026-06-11 14:00 PDT
Track to pick at submission time: **Dynatrace**

---

## Project name
GeminiLens

## Elevator pitch (180 chars max on Devpost)
Local-first observability for Vertex AI Gemini agents. Traces, USD cost, drift, tool egress audit. One Python import, Streamlit dashboard, optional Dynatrace export.

## Inspiration
Every Gemini project I built last year ended up with the same four problems
once it left my laptop: I couldn't tell which prompt was burning my Vertex
AI bill, which agent run had p95 latency creeping up, when the model's
output got noticeably longer than baseline, and which external hosts the
agent's tools had actually called. There are tools for each piece, but they
either lock you into a hosted backend or ask you to install a giant APM
agent. I wanted the smallest thing that solves all four, locally, before I
have to commit to a vendor.

## What it does
GeminiLens wraps any Vertex AI Gemini client and produces a Trace record
per call with prompt, response, token counts, latency, USD cost, and a
list of tool invocations. The library also includes a rolling-vs-baseline
drift report so you can see when latency, cost, or output length is
shifting. An httpx-based egress allowlist enforces that agent tools can
only reach approved hosts.

A Streamlit dashboard renders the traces with live metrics, drift cards,
and a timeline. For production, the Dynatrace exporter pushes every trace
as a structured log event with full gen_ai semantic conventions, so the
same data shows up in Dynatrace notebooks and DQL queries.

## How we built it
- google-genai 1.x for Vertex AI Gemini 2.5 calls
- Streamlit + pandas for the dashboard
- httpx for the egress-guarded transport
- Pure stdlib for cost math and drift, so the math is reviewable
- pytest covering cost, observer, guard, and Dynatrace exporter

The Gemini cost table is hand-curated from Google's published pricing and
lives in the repo so reviewers can audit it without leaving GitHub.

## Challenges we ran into
google-genai's `usage_metadata` shape varies between client versions and
between Vertex AI vs Gemini API. The observer handles both. Drift on a
small trace history is noisy, so we expose the window sizes and sample
counts in the report instead of hiding them.

## Accomplishments we're proud of
Eighteen Python files, fewer than 600 lines of library code, 100 percent
of the public API has tests, runs locally with no GCP credentials via a
synthetic-trace fallback so reviewers can try it without paying anything.

## What we learned
The OpenInference and OpenTelemetry GenAI semantic conventions are still
diverging. Picking conservative attribute names (`gen_ai.usage.input_tokens`)
that work in both worlds keeps the Dynatrace exporter future-proof.

## What's next for GeminiLens
- Multi-process trace stitching for distributed agents
- Vector-store retrieval drift signal
- One-click Arize Phoenix export

## Built with
python, streamlit, vertex-ai, gemini, gemini-2-5, google-genai,
google-cloud-run, dynatrace, httpx, pandas, opentelemetry

## Try it out links (Devpost asks for these)
- Code repo: https://github.com/MukundaKatta/geminilens
- Live demo (Cloud Run): https://geminilens-1029931682737.us-central1.run.app
- Demo video (YouTube unlisted): <PASTE_VIDEO_URL_HERE>

## Submission checklist
- [ ] Code repo URL public on GitHub
- [ ] OSI-approved license visible at repo root (Apache-2.0 — done)
- [ ] Hosted demo URL reachable
- [ ] Demo video 3:00 or under, no copyrighted music
- [ ] Architecture diagram in README or docs (done — ARCHITECTURE.md)
- [ ] Dynatrace track selected on Devpost
- [ ] Country / age confirmation on Devpost
- [ ] Devpost account listed as independent developer (no employer)
