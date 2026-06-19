"""Azure OpenAI / Azure AI Foundry adapter. Same Trace shape as Gemini.

Why this exists: GeminiLens is named for Gemini, but the trace, cost, and
drift code is provider-agnostic. The Agent Academy (Microsoft) hackathon
requires at least one Microsoft product, so we add a thin adapter that wraps
the Azure OpenAI Python SDK and emits the same Trace records.

Pricing source: https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/
(as of 2026-05-17). USD per 1M tokens. Update when pricing changes."""

from __future__ import annotations

import os
import time
import uuid
from contextlib import contextmanager
from typing import Any, Iterator

from geminilens.observer import GeminiObserver, Trace


# Standard tier pricing, USD per 1M tokens. (input, output, cached_input)
_AZURE_OPENAI_PRICING = {
    "gpt-4.1":          (2.00, 8.00, 0.50),
    "gpt-4.1-mini":     (0.40, 1.60, 0.10),
    "gpt-4.1-nano":     (0.10, 0.40, 0.025),
    "gpt-4o":           (2.50, 10.00, 1.25),
    "gpt-4o-mini":      (0.15, 0.60, 0.075),
    "o4-mini":          (1.10, 4.40, 0.275),
    "o3-mini":          (1.10, 4.40, 0.55),
}


def _resolve_azure(model: str) -> tuple[float, float, float] | None:
    prices = _AZURE_OPENAI_PRICING.get(model)
    if prices is not None:
        return prices
    # Prefix fallback for dated / suffixed deployment names (e.g.
    # "gpt-4o-mini-2026-01-01"). Match the *longest* prefix so a "gpt-4o-mini"
    # deployment is not mis-billed at the more expensive "gpt-4o" rate, which
    # is also a matching prefix.
    best: tuple[float, float, float] | None = None
    best_len = -1
    for prefix, p in _AZURE_OPENAI_PRICING.items():
        if model.startswith(prefix) and len(prefix) > best_len:
            best, best_len = p, len(prefix)
    return best


def azure_cost(model: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> float:
    """USD cost for an Azure OpenAI call. Returns 0 for unknown models."""
    prices = _resolve_azure(model)
    if prices is None:
        return 0.0
    in_rate, out_rate, cache_rate = prices
    billable_in = max(0, input_tokens - cached_tokens)
    return round(
        (billable_in * in_rate + output_tokens * out_rate + cached_tokens * cache_rate)
        / 1_000_000,
        6,
    )


class AzureObserver(GeminiObserver):
    """Same observer, Azure-aware cost. Use this in place of GeminiObserver
    when your agent calls Azure OpenAI through the `openai` SDK."""

    def record_response(self, trace: Trace, response: Any) -> None:
        usage = getattr(response, "usage", None)
        if usage is not None:
            trace.input_tokens = int(
                getattr(usage, "prompt_tokens", None)
                or getattr(usage, "input_tokens", None)
                or 0
            )
            trace.output_tokens = int(
                getattr(usage, "completion_tokens", None)
                or getattr(usage, "output_tokens", None)
                or 0
            )
            cached = getattr(usage, "prompt_tokens_details", None)
            if cached is not None:
                trace.cached_tokens = int(getattr(cached, "cached_tokens", 0) or 0)
        choices = getattr(response, "choices", None)
        if choices:
            msg = getattr(choices[0], "message", None)
            if msg is not None:
                trace.response = getattr(msg, "content", "") or ""

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
            tr.cost_usd = azure_cost(tr.model, tr.input_tokens, tr.output_tokens, tr.cached_tokens)
            self.store.append(tr.to_dict())
            if self.on_trace is not None:
                try:
                    self.on_trace(tr)
                except Exception:
                    pass


def make_azure_client():
    """Lazy import + construct an Azure OpenAI client from standard env vars.

    Requires:
        AZURE_OPENAI_ENDPOINT
        AZURE_OPENAI_API_KEY   (or use AzureDefaultCredential outside this helper)
        AZURE_OPENAI_API_VERSION  (default: 2024-10-21)
    """
    try:
        from openai import AzureOpenAI  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "Install `openai>=1.50.0` to use the Azure adapter: pip install openai"
        ) from e
    return AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
    )
