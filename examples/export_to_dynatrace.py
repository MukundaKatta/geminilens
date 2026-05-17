"""Wire the Dynatrace exporter into the observer as a per-trace callback.

Set DT_ENV_URL + DT_API_TOKEN (scope: logs.ingest) and run:

    PYTHONPATH=src python examples/export_to_dynatrace.py
"""

from pathlib import Path

from geminilens import GeminiObserver, TraceStore
from geminilens.agent import simulate
from geminilens.exporters import DynatraceExporter


def main() -> None:
    exporter = DynatraceExporter()  # reads DT_ENV_URL + DT_API_TOKEN from env
    store = TraceStore(Path.home() / ".geminilens" / "traces.jsonl")
    observer = GeminiObserver(
        store=store,
        default_tags={"env": "demo"},
        on_trace=exporter.export_one,  # ship every trace to Dynatrace
    )
    simulate(observer, n=10)
    print("10 traces simulated and pushed to Dynatrace")


if __name__ == "__main__":
    main()
