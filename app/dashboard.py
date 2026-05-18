"""GeminiLens dashboard. Run with: streamlit run app/dashboard.py"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from geminilens import GeminiObserver, TraceStore  # noqa: E402
from geminilens.agent import ResearchAgent, simulate  # noqa: E402
from geminilens.drift import compute_drift  # noqa: E402


TRACE_PATH = os.getenv("GEMINILENS_TRACES", str(Path.home() / ".geminilens" / "traces.jsonl"))


@st.cache_resource
def get_observer() -> GeminiObserver:
    return GeminiObserver(store=TraceStore(TRACE_PATH))


@st.cache_resource
def get_agent() -> ResearchAgent:
    return ResearchAgent(observer=get_observer())


st.set_page_config(page_title="GeminiLens", layout="wide", page_icon=":mag:")
st.title("GeminiLens — observability for Gemini agents")
st.caption(
    "Traces, cost, latency, and drift for any agent built on Vertex AI Gemini. "
    "Open source under Apache 2.0."
)

observer = get_observer()

# Auto-seed on cold start so reviewers see a populated dashboard.
if not observer.store.recent():
    simulate(observer, n=50)

with st.sidebar:
    st.header("Run an agent")
    q = st.text_input("Question", value="What is Vertex AI Agent Builder?")
    use_tool = st.checkbox("Use wiki tool", value=True)
    if st.button("Ask Gemini", type="primary"):
        with st.spinner("calling Gemini..."):
            answer = get_agent().answer(q, use_tool=use_tool)
        st.success("Done.")
        st.write(answer)

    st.divider()
    st.header("Demo data")
    if st.button("Generate 25 synthetic traces"):
        simulate(observer, n=25)
        st.toast("25 traces written")

    st.divider()
    st.caption(f"Trace file: `{TRACE_PATH}`")

traces = observer.store.recent()
if not traces:
    st.info("No traces yet. Use the sidebar to ask Gemini something or seed demo data.")
    st.stop()

df = pd.DataFrame(traces)
df["started_at"] = pd.to_datetime(df["started_at"], unit="s")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Traces", f"{len(df):,}")
c2.metric("Total cost (USD)", f"${df['cost_usd'].sum():.4f}")
c3.metric("p95 latency (ms)", f"{df['latency_ms'].quantile(0.95):.0f}")
err_rate = (df["error"].notna().sum() / len(df)) * 100 if "error" in df.columns else 0.0
c4.metric("Error rate", f"{err_rate:.1f}%")

st.subheader("Drift report")
report = compute_drift(traces)
d1, d2, d3 = st.columns(3)
d1.metric(
    "Latency drift",
    f"{report.latency_drift:.2f}x",
    help=f"rolling p95 {report.latency_p95_rolling_ms}ms vs baseline {report.latency_p95_baseline_ms}ms",
)
d2.metric(
    "Cost drift",
    f"{report.cost_drift:.2f}x",
    help=f"rolling mean ${report.cost_mean_rolling_usd:.5f} vs baseline ${report.cost_mean_baseline_usd:.5f}",
)
d3.metric(
    "Output-length drift",
    f"{report.output_drift:.2f}x",
    help=f"rolling mean {report.out_tokens_mean_rolling:.0f} tok vs baseline {report.out_tokens_mean_baseline:.0f} tok",
)

st.subheader("Latency over time")
st.line_chart(df.set_index("started_at")["latency_ms"], height=200)

st.subheader("Cost over time")
st.bar_chart(df.set_index("started_at")["cost_usd"], height=200)

st.subheader("Recent traces")
display_cols = [
    "started_at",
    "model",
    "input_tokens",
    "output_tokens",
    "cached_tokens",
    "cost_usd",
    "latency_ms",
    "error",
    "tool_calls",
]
available = [c for c in display_cols if c in df.columns]
st.dataframe(df[available].sort_values("started_at", ascending=False).head(50), use_container_width=True)
