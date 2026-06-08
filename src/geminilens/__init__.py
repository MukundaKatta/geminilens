"""GeminiLens: drop-in observability for Gemini (and other LLM) agents.

The core observability building blocks -- tracing, cost accounting, drift
detection and the JSONL trace store -- depend only on the Python standard
library, so they import cleanly even in minimal environments. The
:class:`EgressGuard`, which enforces an outbound-host allowlist, depends on
``httpx`` and is therefore imported lazily: accessing it only pulls ``httpx``
in when you actually use the guard.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from geminilens.cost import CostBreakdown, gemini_cost
from geminilens.drift import DriftReport, compute_drift
from geminilens.observer import GeminiObserver, ToolCall, Trace
from geminilens.store import TraceStore

if TYPE_CHECKING:  # pragma: no cover - typing only
    from geminilens.guard import EgressBlocked, EgressGuard

__all__ = [
    "GeminiObserver",
    "Trace",
    "ToolCall",
    "TraceStore",
    "CostBreakdown",
    "gemini_cost",
    "DriftReport",
    "compute_drift",
    "EgressGuard",
    "EgressBlocked",
    "__version__",
]

# Keep in sync with ``[project].version`` in pyproject.toml.
__version__ = "0.2.0"

# Names that live in modules with heavier (non-stdlib) dependencies. They are
# resolved on first access via PEP 562 ``__getattr__`` so that importing
# ``geminilens`` never requires those dependencies unless the feature is used.
_LAZY = {
    "EgressGuard": "geminilens.guard",
    "EgressBlocked": "geminilens.guard",
}


def __getattr__(name: str):
    module_path = _LAZY.get(name)
    if module_path is not None:
        import importlib

        module = importlib.import_module(module_path)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
