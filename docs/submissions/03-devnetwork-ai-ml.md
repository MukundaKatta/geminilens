# DevNetwork AI+ML Hackathon 2026

Devpost: https://devnetwork-ai-ml-hack-2026.devpost.com
Deadline: 2026-05-28 10:00 PDT (the tight one)

This event has sponsor tracks. Best fits for GeminiLens:
- **TrueFoundry** ($1,500): they sell LLM observability themselves, so a
  local dev tool that complements their hosted platform is on-message.
- Skip Perfect Corp ($2,500): beauty-tech APIs, not a fit.

---

## Project name
GeminiLens

## One-liner
Local-first LLM observability that exports to TrueFoundry for production.

## Why TrueFoundry track
TrueFoundry's pitch is one platform for LLM apps in production: gateway,
observability, deployments. GeminiLens fills the gap *before* production:
the seconds when a developer is iterating on a Gemini or Azure OpenAI agent
on their laptop, before they're ready to send traces to a hosted backend.
The exporter ships traces to TrueFoundry once you're ready to graduate the
project.

## What works today
- Gemini and Azure OpenAI adapters share one Trace shape
- Drift, cost, and tool-egress audit
- Streamlit dashboard
- Dynatrace exporter wired (TrueFoundry exporter scaffolded as a TODO,
  pending TrueFoundry account so we can hit a real ingest endpoint)

## Submission requirements
- Public web/mobile app: yes, Streamlit dashboard hosted somewhere
- Devpost project page with short write-up and screenshots: README has
  what we need
- Demo video 1-3 minutes: trim the 3-min demo script to 1:30

## Try it out
- Code repo: https://github.com/MukundaKatta/geminilens
- Hosted dashboard: https://geminilens-1029931682737.us-central1.run.app
- Demo video: https://storage.googleapis.com/geminilens-demo-mukunda/geminilens-demo.mp4

## Open question before submitting
Do we have a TrueFoundry account? If not, signup is free with a work
email. Until we hit a real TF ingest endpoint, the exporter stays a stub.

## Submission checklist
- [ ] DevNetwork registration (free)
- [ ] TrueFoundry account (free signup)
- [ ] Implement `truefoundry_exporter.py` against real TF ingest endpoint
- [ ] Hosted dashboard URL
- [ ] 1:30 demo video
- [ ] Submit on Devpost by 2026-05-28 10:00 PDT
