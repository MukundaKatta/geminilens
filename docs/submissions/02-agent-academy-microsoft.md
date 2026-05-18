# Agent Academy Hackathon (Microsoft)

Page: https://microsoft.github.io/agent-academy/events/hackathon/
Deadline: 2026-06-02 23:59 PT
Required: at least one Microsoft product. We use **Azure OpenAI**.

---

## Project name
GeminiLens for Azure OpenAI

## Tagline
The same trace + cost + drift wrapper, this time for Azure OpenAI agents.

## What we built
Took the existing GeminiLens observability core and added an `AzureObserver`
adapter that wraps Azure OpenAI calls and produces the identical Trace
record shape. The Streamlit dashboard works against either source. The cost
table is the published Azure OpenAI pricing for gpt-4.1, gpt-4.1-mini,
gpt-4.1-nano, gpt-4o, gpt-4o-mini, o3-mini, and o4-mini.

## Microsoft products used
- Azure OpenAI Service (gpt-4o + gpt-4.1-mini)
- Azure Container Apps for hosting the dashboard

## Architecture overview (Agent Academy explicitly asks for this)
Three layers:
1. **Library**: `AzureObserver` context manager, `azure_cost()` calculator,
   drift report, JSONL trace store, optional egress allowlist.
2. **Reference agent**: a small research agent that takes a question,
   optionally calls one allowlisted tool (Wikipedia summary), then asks
   Azure OpenAI for an answer. Falls back to a deterministic response when
   credentials are missing so the demo works offline.
3. **Dashboard**: Streamlit page with top-line metrics, drift cards,
   latency and cost charts, and the last 50 traces in a table.

Data flow: agent code → AzureObserver context → Azure OpenAI client →
response usage extracted → Trace appended to JSONL + in-memory ring →
dashboard re-reads and rerenders.

## Target user
Developers shipping Azure OpenAI agents who want to see cost, latency, and
drift locally during development without committing to a hosted backend.

## Demo video script (under 5 minutes)
Same script as the Google Cloud submission (`docs/demo-script.md`), with the
Vertex AI call replaced by an Azure OpenAI call to the gpt-4o-mini
deployment. Show the dashboard updating, then trigger drift by sending three
longer prompts, then show the cost-per-call math against the Azure pricing
table in the README.

## Try it out
- Code repo: https://github.com/MukundaKatta/geminilens
- Live demo (Cloud Run, runs the Gemini side; Azure adapter shown via tests + code walkthrough in the video): https://geminilens-1029931682737.us-central1.run.app
- Demo video (MP4, public GCS): https://storage.googleapis.com/geminilens-demo-mukunda/geminilens-demo.mp4

## What's left before submission
- [ ] Azure subscription with credit on it
- [ ] Azure OpenAI resource + a gpt-4o-mini deployment
- [ ] Set AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY locally and confirm
      the AzureObserver tests produce traces from real responses
- [ ] Deploy Dockerfile to Azure Container Apps
- [ ] Record the 5-min video (gift cards, not cash, so don't burn too much
      time polishing)
- [ ] Submit on the Agent Academy submission form (link in their site)
