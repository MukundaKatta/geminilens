"""Streamlit page: ask the Dynatrace Triage Agent.

Additive page for the GeminiLens dashboard. Run the dashboard as usual
(`streamlit run app/dashboard.py`) and this shows up as a second page in the nav.

The triage agent (Gemini 3 + Google Cloud Agent Builder/ADK + Dynatrace MCP)
lives in `examples/dynatrace_triage_agent/`. It needs google-adk installed and
GOOGLE_CLOUD_PROJECT + DT_ENVIRONMENT + DT_PLATFORM_TOKEN set. Until then this
page shows setup guidance instead of failing, so reviewers always see a working
dashboard.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import streamlit as st

REPO = Path(__file__).resolve().parents[2]
for sub in ("src", "examples"):
    p = str(REPO / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

st.set_page_config(page_title="Triage Agent", layout="wide", page_icon=":rotating_light:")
st.title("Ask the Dynatrace Triage Agent")
st.caption(
    "Gemini 3 + Google Cloud Agent Builder (ADK) + Dynatrace MCP. "
    "Every model call is observed by GeminiLens."
)

with st.expander("Setup (needed once before the agent can answer)"):
    st.markdown(
        "1. `pip install -r examples/dynatrace_triage_agent/requirements.txt`\n"
        "2. Set `GOOGLE_CLOUD_PROJECT`, `DT_ENVIRONMENT`, `DT_PLATFORM_TOKEN` "
        "(see `examples/dynatrace_triage_agent/.env.example`)\n"
        "3. `gcloud auth application-default login`\n"
        "4. Verify with `python examples/dynatrace_triage_agent/preflight.py`"
    )

question = st.text_input(
    "Ask about live problems",
    value="What blew up in the last hour?",
    help="Free-text incident question. The agent uses Dynatrace MCP tools to answer.",
)

if st.button("Ask the triage agent", type="primary"):
    try:
        from dynatrace_triage_agent.run_local import ask
    except Exception as e:
        st.error(f"Triage agent not ready: {type(e).__name__}: {e}")
        st.info(
            "Install google-adk and set the env vars in the Setup section above, "
            "then reload this page."
        )
    else:
        try:
            with st.spinner("querying Dynatrace via the triage agent..."):
                answer = asyncio.run(ask(question))
            st.success("Done.")
            st.write(answer or "(the agent returned no text)")
        except Exception as e:
            st.error(f"Agent call failed: {type(e).__name__}: {e}")

st.divider()
st.subheader("GeminiLens - the agent's own telemetry")
st.caption(
    "Wire the after_model_callback in examples/dynatrace_triage_agent/agent.py "
    "(see its comment) so every triage call lands here as cost + latency."
)

try:
    import pandas as pd

    from geminilens import TraceStore

    trace_path = os.getenv(
        "GEMINILENS_TRACES", str(Path.home() / ".geminilens" / "traces.jsonl")
    )
    rows = list(TraceStore(trace_path).load_file())
    if rows:
        df = pd.DataFrame(rows)
        c1, c2, c3 = st.columns(3)
        c1.metric("Traces", f"{len(df):,}")
        if "cost_usd" in df.columns:
            c2.metric("Total cost (USD)", f"${df['cost_usd'].sum():.4f}")
        if "latency_ms" in df.columns:
            c3.metric("p95 latency (ms)", f"{df['latency_ms'].quantile(0.95):.0f}")
        cols = [
            c
            for c in (
                "started_at",
                "model",
                "input_tokens",
                "output_tokens",
                "cost_usd",
                "latency_ms",
                "error",
            )
            if c in df.columns
        ]
        st.dataframe(df[cols].tail(50), use_container_width=True)
    else:
        st.info(f"No traces yet at `{trace_path}`.")
except Exception as e:
    st.warning(f"Trace feed unavailable: {type(e).__name__}: {e}")
