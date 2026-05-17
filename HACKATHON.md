# Hackathon submission notes

This project targets three hackathons. Same core repo, three submission
forms.

| Hackathon | Deadline | Track | Status |
|---|---|---|---|
| [Google Cloud Rapid Agent](https://rapid-agent.devpost.com/) | 2026-06-11 | Dynatrace (best fit) | priority |
| [Agent Academy (Microsoft)](https://microsoft.github.io/agent-academy/events/hackathon/) | 2026-06-02 | needs Azure adapter | second |
| [DevNetwork AI+ML 2026](https://devnetwork-ai-ml-hack-2026.devpost.com/) | 2026-05-28 | TrueFoundry sponsor track | third |

## Google Cloud Rapid Agent — Dynatrace track

### Project title
GeminiLens: Local-First Observability for Vertex AI Gemini Agents

### Elevator pitch (under 200 chars)
Drop-in observability for Gemini agents. Traces, USD cost, drift, and tool
egress audit. One Python import, one Streamlit dashboard, optional export to
Dynatrace.

### What it does (paste into Devpost "Description")
GeminiLens is a small open-source library plus dashboard that gives Gemini
agent builders the four numbers they care about during development: cost per
call, p95 latency, output drift over time, and a full audit log of every
external host an agent's tools reached. It wraps a Vertex AI Gemini client
without forcing you onto a hosted backend. A Streamlit dashboard renders the
traces locally and a one-line exporter pushes them to Dynatrace for
production monitoring.

### How we built it
- Python 3.10+
- google-genai for Vertex AI Gemini 2.5 calls
- httpx custom transport for the egress allowlist
- Streamlit + pandas for the dashboard
- Pure stdlib for cost math and drift computation, so the math is auditable
  and there is nothing to mock in tests

The cost table is hand-curated from Google's published Gemini pricing and is
checked into the repo so reviewers can see what we charge against.

### Challenges
- google-genai's `usage_metadata` shape varies between client versions and
  between Vertex AI vs API. The observer handles both shapes.
- Drift over a small number of traces is noisy. We split rolling and baseline
  windows explicitly so reviewers can see the sample counts.

### Built with
- Vertex AI
- Gemini 2.5
- Python
- Streamlit
- httpx
- pandas
- Dynatrace (exporter)

### Required submission fields
- Public GitHub URL: `https://github.com/MukundaKatta/geminilens` (after push)
- Demo video: 3 min, screen recording of the dashboard with a real Vertex AI
  call. Script in `docs/demo-script.md`.
- Architecture diagram: see `ARCHITECTURE.md`.
- Track: Dynatrace.
- License: Apache-2.0 (visible in repo root).

## Agent Academy (Microsoft)

Same library, plus an Azure AI Foundry / Azure OpenAI adapter so the agent
can run on `gpt-4o` or `gpt-4.1` through Azure. Add `azure_observer.py` that
shapes the Azure OpenAI response into the same Trace record. Reuse the
dashboard verbatim.

Hackathon requirement: must use at least one Microsoft product. Azure OpenAI
qualifies.

Submission needs Microsoft Innovation Studio account, which requires Azure
credentials. Open question for builder: do we have Azure?

## DevNetwork AI+ML 2026

TrueFoundry sponsor track ($1,500). TrueFoundry is itself an LLM observability
platform, so the pitch is "GeminiLens as a TrueFoundry-compatible local
dev tool that exports traces to TrueFoundry for production." Add a small
`truefoundry_exporter.py` that POSTs traces to their ingest endpoint.

Hackathon also has a $2,500 Perfect Corp prize but that's beauty-tech APIs
and a poor fit.

## What's left before submission

- [ ] Push to `github.com/MukundaKatta/geminilens` (private until reviewed,
      then public for the OSI-license requirement)
- [ ] Deploy a hosted demo URL (Cloud Run or Streamlit Cloud)
- [ ] Record 3-minute demo video
- [ ] Register on Devpost as Mukunda Katta, list as independent developer
- [ ] Submit to Google Cloud Rapid Agent, Dynatrace track
- [ ] Build Azure adapter and submit to Agent Academy
- [ ] Build TrueFoundry exporter and submit to DevNetwork
