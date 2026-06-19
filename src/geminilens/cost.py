"""Gemini cost calculator. Prices in USD per 1M tokens, sourced from
https://ai.google.dev/gemini-api/docs/pricing as of 2026-05-17.
Update when pricing changes."""

from dataclasses import dataclass

# Tiered pricing: (input_le_128k, input_gt_128k, output_le_128k, output_gt_128k)
# Cached input priced separately; cache-storage cost is per-hour and skipped here.
_PRICING_USD_PER_M = {
    "gemini-2.5-pro":         (1.25, 2.50, 10.00, 15.00),
    "gemini-2.5-flash":       (0.30, 0.30,  2.50,  2.50),
    "gemini-2.5-flash-lite":  (0.10, 0.10,  0.40,  0.40),
    "gemini-2.0-flash":       (0.10, 0.10,  0.40,  0.40),
    "gemini-2.0-flash-lite":  (0.075, 0.075, 0.30, 0.30),
}

_THRESHOLD = 128_000


@dataclass(frozen=True)
class CostBreakdown:
    model: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    input_usd: float
    output_usd: float
    cached_usd: float
    total_usd: float


def _resolve(model: str) -> tuple[float, float, float, float] | None:
    if model in _PRICING_USD_PER_M:
        return _PRICING_USD_PER_M[model]
    # Prefix fallback for dated / suffixed model ids (e.g.
    # "gemini-2.5-flash-lite-preview-2026"). Match the *longest* prefix so that
    # more specific families win: "gemini-2.5-flash-lite-..." must resolve to
    # flash-lite pricing, not the cheaper-but-wrong "gemini-2.5-flash" prefix
    # that also matches. Matching by insertion order would mis-bill these.
    best: tuple[float, float, float, float] | None = None
    best_len = -1
    for prefix, prices in _PRICING_USD_PER_M.items():
        if model.startswith(prefix) and len(prefix) > best_len:
            best, best_len = prices, len(prefix)
    return best


def gemini_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
) -> CostBreakdown:
    """Compute USD cost for a Gemini call. Returns zeros if model is unknown."""
    prices = _resolve(model)
    if prices is None:
        return CostBreakdown(model, input_tokens, output_tokens, cached_tokens, 0, 0, 0, 0)

    in_lo, in_hi, out_lo, out_hi = prices
    over = input_tokens > _THRESHOLD

    billable_input = max(0, input_tokens - cached_tokens)
    input_rate = in_hi if over else in_lo
    output_rate = out_hi if over else out_lo
    cache_rate = input_rate * 0.25  # Gemini cached-input is ~25% of standard input

    input_usd = billable_input * input_rate / 1_000_000
    output_usd = output_tokens * output_rate / 1_000_000
    cached_usd = cached_tokens * cache_rate / 1_000_000

    return CostBreakdown(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=cached_tokens,
        input_usd=round(input_usd, 6),
        output_usd=round(output_usd, 6),
        cached_usd=round(cached_usd, 6),
        total_usd=round(input_usd + output_usd + cached_usd, 6),
    )
