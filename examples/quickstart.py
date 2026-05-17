"""Five-line quickstart.

    python examples/quickstart.py

Generates synthetic traces, writes them to ~/.geminilens/traces.jsonl, and
prints a drift report. Useful for verifying the install before plugging in
your real Gemini key."""

from pathlib import Path

from geminilens import GeminiObserver, TraceStore
from geminilens.agent import simulate
from geminilens.drift import compute_drift


def main() -> None:
    store = TraceStore(Path.home() / ".geminilens" / "traces.jsonl")
    observer = GeminiObserver(store=store, default_tags={"env": "demo"})
    simulate(observer, n=120)
    report = compute_drift(observer.store.recent())
    print(f"traces stored: {len(observer.store.recent())}")
    print(f"latency drift: {report.latency_drift:.2f}x")
    print(f"cost drift:    {report.cost_drift:.2f}x")
    print(f"output drift:  {report.output_drift:.2f}x")


if __name__ == "__main__":
    main()
