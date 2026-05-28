# Dynatrace Triage Agent

A Gemini 3 agent built with Google Cloud Agent Builder (ADK) that connects to the
Dynatrace hosted MCP server, lets you ask natural-language questions about live
problems, and answers in plain English. Built for the Google Cloud Rapid Agent
Hackathon, Dynatrace track.

> STATUS: API verified 2026-05-28 against current ADK (google-adk) and the Dynatrace
> remote MCP docs. The ADK imports, streamable-HTTP params, gateway URL, and Bearer /
> Platform-Token auth are confirmed. Still untested against a live tenant: run it with
> your own Google Cloud project and Dynatrace environment before you submit.

## What you need first (cannot be created for you)

- A Google Cloud project with Vertex AI enabled, and `gcloud auth application-default login`.
- A Dynatrace SaaS environment URL, for example `https://abc12345.apps.dynatrace.com`.
- A Dynatrace Platform Token with the gateway scopes `mcp-gateway:servers:invoke`
  and `mcp-gateway:servers:read`, plus the tool scopes you will use (for example
  `storage:buckets:read`, `storage:logs:read`, `storage:entities:read`,
  `davis-copilot:nl2dql:execute`). The token only works within your own permission scope.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in your real values
python preflight.py    # sanity-check deps, env, and the MCP URL before adk run
```

## Run

Primary path, ADK CLI (auto-discovers `root_agent`):

```bash
# from the directory that contains this folder (the repo's examples/ dir)
adk run dynatrace_triage_agent
# or a local web UI:
adk web
```

Programmatic path (for embedding behind Streamlit):

```bash
python -m dynatrace_triage_agent.run_local "what blew up in the last hour?"
```

## How it maps to the rules

- Agent Builder / ADK: `LlmAgent` in `agent.py` (rule 1).
- Partner MCP: `MCPToolset` over the Dynatrace remote MCP gateway (rule 2).
- Public repo + OSS license: this folder lives in the geminilens repo at
  `examples/dynatrace_triage_agent/` (Apache-2.0 from the repo root).
- Dashboard UI: the geminilens dashboard exposes an "Ask the Triage Agent" page
  (`app/pages/1_Ask_the_Triage_Agent.py`) wired to this agent.
- 3-minute demo video: record the agent answering two live questions, then the
  GeminiLens dashboard showing the agent's own cost and latency.

## Next steps

1. Fill `.env` (or export the vars), then run `python preflight.py` to confirm
   deps, env, and the MCP URL.
2. Run `adk run dynatrace_triage_agent` and confirm tools load and a question
   returns real Dynatrace data.
3. Wire the optional GeminiLens `after_model_callback` (commented in `agent.py`)
   so each triage call lands in the dashboard's telemetry panel.
4. Deploy to Cloud Run.
5. Record the video and submit on https://rapid-agent.devpost.com/ before
   2026-06-11 2:00 PM PDT.

The paste-ready Devpost form text lives in the hackathon working directory's
`SUBMISSION.md` (not copied into this repo).

## References

- ADK MCP tools: https://google.github.io/adk-docs/tools-custom/mcp-tools/
- Dynatrace MCP server: https://docs.dynatrace.com/docs/dynatrace-intelligence/dynatrace-mcp
- dynatrace-oss/dynatrace-mcp: https://github.com/dynatrace-oss/dynatrace-mcp
