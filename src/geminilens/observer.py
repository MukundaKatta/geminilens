"""Core observer: wraps google-genai Gemini calls to capture traces,
cost, latency, drift signal, and tool-call audit. Designed to be a drop-in
context manager around any Gemini agent loop."""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Iterator

from geminilens.cost import gemini_cost, CostBreakdown
from geminilens.store import TraceStore


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    result: Any
    duration_ms: float
    error: str | None = None


@dataclass
class Trace:
    trace_id: str
    model: str
    started_at: float
    ended_at: float | None = None
    prompt: str = ""
    response: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    tool_calls: list[ToolCall] = field(default_factory=list)
    error: str | None = None
    tags: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


class GeminiObserver:
    """Wraps a `google.genai.Client` (or any callable returning a Gemini-shaped
    response) and emits Trace records on every call."""

    def __init__(
        self,
        store: TraceStore | None = None,
        default_tags: dict[str, str] | None = None,
        on_trace: Callable[[Trace], None] | None = None,
    ):
        self.store = store or TraceStore()
        self.default_tags = dict(default_tags or {})
        self.on_trace = on_trace

    @contextmanager
    def trace(self, model: str, prompt: str = "", **tags: str) -> Iterator[Trace]:
        tr = Trace(
            trace_id=uuid.uuid4().hex,
            model=model,
            started_at=time.time(),
            prompt=prompt,
            tags={**self.default_tags, **tags},
        )
        t0 = time.perf_counter()
        try:
            yield tr
        except Exception as e:
            tr.error = f"{type(e).__name__}: {e}"
            raise
        finally:
            tr.ended_at = time.time()
            tr.latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            cost = gemini_cost(
                model=tr.model,
                input_tokens=tr.input_tokens,
                output_tokens=tr.output_tokens,
                cached_tokens=tr.cached_tokens,
            )
            tr.cost_usd = cost.total_usd
            self.store.append(tr.to_dict())
            if self.on_trace is not None:
                try:
                    self.on_trace(tr)
                except Exception:
                    pass  # observer must never break the agent

    def record_response(self, trace: Trace, response: Any) -> None:
        """Extract usage from a google-genai response and attach to the trace.
        Works against responses with a `usage_metadata` attribute (google-genai)
        or a `usage` dict (OpenAI-shaped)."""
        usage = getattr(response, "usage_metadata", None) or getattr(response, "usage", None)
        if usage is not None:
            trace.input_tokens = int(
                getattr(usage, "prompt_token_count", None)
                or getattr(usage, "input_tokens", None)
                or (usage.get("prompt_token_count") if isinstance(usage, dict) else 0)
                or 0
            )
            trace.output_tokens = int(
                getattr(usage, "candidates_token_count", None)
                or getattr(usage, "output_tokens", None)
                or (usage.get("candidates_token_count") if isinstance(usage, dict) else 0)
                or 0
            )
            trace.cached_tokens = int(
                getattr(usage, "cached_content_token_count", None)
                or (usage.get("cached_content_token_count") if isinstance(usage, dict) else 0)
                or 0
            )
        text = getattr(response, "text", None)
        if text:
            trace.response = text

    def record_tool_call(
        self,
        trace: Trace,
        name: str,
        args: dict[str, Any],
        result: Any,
        duration_ms: float,
        error: str | None = None,
    ) -> None:
        trace.tool_calls.append(
            ToolCall(name=name, args=args, result=result, duration_ms=duration_ms, error=error)
        )

    def run_tool(
        self,
        trace: Trace,
        name: str,
        fn: Callable[..., Any],
        *args,
        **kwargs,
    ) -> Any:
        """Helper: invoke a tool, record timing + result on the trace."""
        t0 = time.perf_counter()
        err: str | None = None
        result: Any = None
        try:
            result = fn(*args, **kwargs)
            return result
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            raise
        finally:
            dur = round((time.perf_counter() - t0) * 1000, 2)
            self.record_tool_call(
                trace,
                name=name,
                args={"args": args, "kwargs": kwargs},
                result=result if err is None else None,
                duration_ms=dur,
                error=err,
            )
