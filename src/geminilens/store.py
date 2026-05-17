"""Append-only JSONL trace store. Keeps a hot in-memory ring buffer of the
last N traces for the dashboard, plus a durable file for replay/eval."""

from __future__ import annotations

import json
import threading
from collections import deque
from pathlib import Path
from typing import Any, Iterable


class TraceStore:
    def __init__(self, path: str | Path | None = None, in_memory_cap: int = 5000):
        self._path = Path(path) if path else None
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.touch(exist_ok=True)
        self._buf: deque[dict[str, Any]] = deque(maxlen=in_memory_cap)
        self._lock = threading.Lock()

    def append(self, record: dict[str, Any]) -> None:
        line = json.dumps(record, separators=(",", ":"), default=str)
        with self._lock:
            self._buf.append(record)
            if self._path is not None:
                with self._path.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")

    def recent(self, limit: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            data = list(self._buf)
        if limit is None:
            return data
        return data[-limit:]

    def load_file(self) -> Iterable[dict[str, Any]]:
        if self._path is None or not self._path.exists():
            return []
        out = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out
