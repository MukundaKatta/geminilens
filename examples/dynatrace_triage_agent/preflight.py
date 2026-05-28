"""Preflight check for the Dynatrace Triage Agent.

Run this FIRST in your hands-on session, before `adk run`. It validates that the
ADK is installed, the required env vars are set, and the Dynatrace MCP URL is
well formed, so you find configuration gaps in one shot instead of one failed
`adk run` at a time.

    # from inside the folder (works even before deps are installed):
    python preflight.py

Run it as a standalone file, not `python -m dynatrace_triage_agent.preflight`:
the package __init__ eagerly imports the agent (so `adk run` can discover it),
which would fail here if google-adk is not installed yet, which is exactly the
gap this script is meant to report cleanly.

Exit code 0 means all required checks passed. Non-zero means fix something first.
"""

from __future__ import annotations

import os
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass  # dotenv is optional; env can be exported directly


PASS = "[PASS]"
WARN = "[WARN]"
FAIL = "[FAIL]"


def _check_import(module_path: str, symbol: str, hint: str) -> bool:
    try:
        mod = __import__(module_path, fromlist=[symbol])
        getattr(mod, symbol)
        print(f"{PASS} import {module_path}.{symbol}")
        return True
    except Exception as e:  # ImportError or AttributeError
        print(f"{FAIL} import {module_path}.{symbol}: {type(e).__name__}: {e}")
        print(f"       fix: {hint}")
        return False


def _check_env(name: str, *, required: bool, hint: str, secret: bool = False) -> bool:
    val = os.environ.get(name, "")
    placeholderish = val.startswith("REPLACE_WITH") or "YOUR-ENV" in val or "your-gcp" in val
    if val and not placeholderish:
        shown = "set" if secret else val
        print(f"{PASS} {name} = {shown}")
        return True
    marker = FAIL if required else WARN
    state = "still a placeholder" if placeholderish else "not set"
    print(f"{marker} {name} {state}")
    print(f"       {'fix' if required else 'note'}: {hint}")
    return not required


def main() -> int:
    print("Dynatrace Triage Agent - preflight\n")
    ok = True

    print("Dependencies:")
    ok &= _check_import("google.adk.agents", "LlmAgent", "pip install -r requirements.txt")
    ok &= _check_import(
        "google.adk.tools.mcp_tool", "MCPToolset", "pip install -r requirements.txt"
    )
    ok &= _check_import("google.genai", "types", "pip install -r requirements.txt")

    print("\nGoogle Cloud / Vertex:")
    ok &= _check_env(
        "GOOGLE_CLOUD_PROJECT", required=True, hint="set to your GCP project id"
    )
    _check_env("GOOGLE_CLOUD_LOCATION", required=False, hint="defaults to us-central1")
    _check_env(
        "GOOGLE_GENAI_USE_VERTEXAI",
        required=False,
        hint="set TRUE to route through Vertex AI",
    )
    _check_env("TRIAGE_MODEL", required=False, hint="defaults to gemini-3-pro")

    adc = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    default_adc = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")
    if adc and os.path.exists(adc):
        print(f"{PASS} ADC file at GOOGLE_APPLICATION_CREDENTIALS")
    elif os.path.exists(default_adc):
        print(f"{PASS} ADC present (gcloud application-default login)")
    else:
        print(f"{WARN} no Application Default Credentials found")
        print("       note: run `gcloud auth application-default login`")

    print("\nDynatrace remote MCP:")
    env_ok = _check_env(
        "DT_ENVIRONMENT",
        required=True,
        hint="set to your env URL, e.g. https://abc12345.apps.dynatrace.com",
    )
    ok &= env_ok
    ok &= _check_env(
        "DT_PLATFORM_TOKEN",
        required=True,
        secret=True,
        hint="Platform Token with mcp-gateway:servers:invoke + :read and tool scopes",
    )

    dt_env = os.environ.get("DT_ENVIRONMENT", "").rstrip("/")
    if dt_env:
        if not dt_env.startswith("https://"):
            print(f"{WARN} DT_ENVIRONMENT should start with https://")
        if ".live.dynatrace.com" in dt_env:
            print(f"{WARN} DT_ENVIRONMENT looks like a classic (.live.) URL")
            print("       note: the MCP gateway expects the .apps.dynatrace.com URL")
        mcp_url = f"{dt_env}/platform-reserved/mcp-gateway/v0.1/servers/dynatrace-mcp/mcp"
        print(f"       MCP endpoint: {mcp_url}")

    print("\nOptional GeminiLens closed-loop exporter:")
    _check_env(
        "DT_ENV_URL",
        required=False,
        hint="classic .live. URL, only for shipping traces back as logs",
    )
    _check_env(
        "DT_API_TOKEN",
        required=False,
        secret=True,
        hint="needs the logs.ingest scope; only for the exporter",
    )

    print()
    if ok:
        print(f"{PASS} required checks passed. Next: adk run dynatrace_triage_agent")
        return 0
    print(f"{FAIL} fix the items above, then re-run this check.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
