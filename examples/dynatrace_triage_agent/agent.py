"""Dynatrace Triage Agent - Gemini 3 + Google Cloud Agent Builder (ADK) + Dynatrace MCP.

STATUS: API verified 2026-05-28 against current ADK (google-adk) and the Dynatrace
remote MCP docs below. The ADK imports, the streamable-HTTP connection params, the
gateway URL, and the Bearer / Platform-Token auth are all confirmed. Still untested
against a live tenant: run it with your own Google Cloud project and Dynatrace
environment to confirm it end to end before you submit.

Docs:
- ADK MCP tools: https://google.github.io/adk-docs/tools-custom/mcp-tools/
- Dynatrace remote MCP: https://docs.dynatrace.com/docs/dynatrace-intelligence/dynatrace-mcp
- Dynatrace remote MCP migration: https://github.com/dynatrace-oss/dynatrace-mcp/blob/main/docs/remote-mcp-migration.md
"""

import os

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import MCPToolset, StreamableHTTPConnectionParams

# Gemini 3 model id. "gemini-3-pro" is a current Gemini 3 id; "gemini-3.1-pro" is the
# newer revision. Override via the TRIAGE_MODEL env var if your Vertex project needs
# a different string.
MODEL = os.environ.get("TRIAGE_MODEL", "gemini-3-pro")


def _dynatrace_mcp_url() -> str:
    env = os.environ.get("DT_ENVIRONMENT", "").rstrip("/")
    if not env:
        raise RuntimeError(
            "Set DT_ENVIRONMENT to your Dynatrace env URL, "
            "for example https://abc12345.apps.dynatrace.com"
        )
    return f"{env}/platform-reserved/mcp-gateway/v0.1/servers/dynatrace-mcp/mcp"


def _dynatrace_token() -> str:
    token = os.environ.get("DT_PLATFORM_TOKEN", "")
    if not token:
        raise RuntimeError(
            "Set DT_PLATFORM_TOKEN to a Dynatrace Platform Token with scopes "
            "mcp-gateway:servers:invoke and mcp-gateway:servers:read"
        )
    return token


# Live problems, services, and DQL access over Dynatrace's hosted MCP gateway.
dynatrace_tools = MCPToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=_dynatrace_mcp_url(),
        headers={"Authorization": f"Bearer {_dynatrace_token()}"},
    ),
)

root_agent = LlmAgent(
    model=MODEL,
    name="dynatrace_triage_agent",
    instruction=(
        "You are an incident triage assistant. Use the Dynatrace tools to fetch "
        "live problems, affected services, and DQL query results. Answer in plain "
        "English: name the affected service, summarize the likely impact, and "
        "include the Dynatrace problem id or a link when available. If the tools "
        "return no data, say so plainly instead of guessing."
    ),
    tools=[dynatrace_tools],
    # Differentiator (optional): wrap every model call with GeminiLens so the
    # agent reports its own cost, latency, and drift. ADK's after_model_callback
    # fits here. Confirmed signature: (callback_context, llm_response); return None
    # to keep the model response, or return an LlmResponse to override it.
    #
    # GeminiLens API verified against the geminilens package (v0.1.0):
    # GeminiObserver.trace(model, prompt="", **tags) is a context manager that
    # yields a Trace and emits cost/latency on exit; record_response(trace, resp)
    # pulls usage from resp.usage_metadata, which ADK's LlmResponse carries.
    #
    #   from geminilens import GeminiObserver
    #   _obs = GeminiObserver()
    #   def after_model(callback_context, llm_response):
    #       with _obs.trace(model=MODEL) as tr:
    #           _obs.record_response(tr, llm_response)
    #       return None
    #   ... pass after_model_callback=after_model to LlmAgent above
    #
    # Closed-loop story (optional): also ship each trace back to Dynatrace as a
    # structured log. DynatraceExporter posts to /api/v2/logs/ingest and needs a
    # SEPARATE credential from the MCP gateway above: DT_ENV_URL (classic env,
    # e.g. https://abc12345.live.dynatrace.com) and DT_API_TOKEN with the
    # logs.ingest scope. Wire it via the observer's on_trace hook (fires on
    # context-manager exit, already wrapped so it can never break the agent):
    #
    #   from geminilens.exporters.dynatrace import DynatraceExporter
    #   _exporter = DynatraceExporter()  # reads DT_ENV_URL + DT_API_TOKEN
    #   _obs = GeminiObserver(on_trace=_exporter.export_one)
)
