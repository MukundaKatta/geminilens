"""Trivial sink: append each trace to a JSONL file. Useful for piping into
Arize Phoenix's local viewer or for cold-storage replay."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from geminilens.observer import Trace


class JsonlFileExporter:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def export(self, traces: Iterable[Trace | dict]) -> int:
        n = 0
        with self.path.open("a", encoding="utf-8") as f:
            for t in traces:
                d = t.to_dict() if isinstance(t, Trace) else t
                f.write(json.dumps(d, default=str) + "\n")
                n += 1
        return n

    def export_one(self, trace: Trace | dict) -> None:
        self.export([trace])
