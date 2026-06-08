"""Standard-library unittest coverage for geminilens.cost.

Runs with no third-party dependencies:

    python3 -m unittest discover -s tests/unit
"""

import os
import sys
import unittest

# Make ``src`` importable without requiring PYTHONPATH to be set.
_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, os.path.abspath(_SRC))

from geminilens.cost import CostBreakdown, gemini_cost  # noqa: E402


class GeminiCostTests(unittest.TestCase):
    def test_flash_under_threshold(self):
        cost = gemini_cost("gemini-2.5-flash", input_tokens=1_000_000, output_tokens=500_000)
        # 1M input @ 0.30 + 500k output @ 2.50 = 0.30 + 1.25 = 1.55
        self.assertEqual(cost.input_usd, 0.30)
        self.assertEqual(cost.output_usd, 1.25)
        self.assertEqual(cost.total_usd, 1.55)

    def test_pro_over_threshold(self):
        cost = gemini_cost("gemini-2.5-pro", input_tokens=200_000, output_tokens=10_000)
        # Over 128k: input 2.50, output 15.00 per 1M.
        self.assertEqual(cost.input_usd, 0.50)
        self.assertEqual(cost.output_usd, 0.15)
        self.assertEqual(cost.total_usd, 0.65)

    def test_cached_input_discount(self):
        cost = gemini_cost(
            "gemini-2.5-flash",
            input_tokens=1_000_000,
            output_tokens=0,
            cached_tokens=500_000,
        )
        # 500k billable @ 0.30 + 500k cached @ 0.075 (=25% of 0.30).
        self.assertEqual(cost.input_usd, 0.15)
        self.assertEqual(cost.cached_usd, 0.0375)
        self.assertEqual(cost.total_usd, 0.1875)

    def test_unknown_model_returns_zero(self):
        cost = gemini_cost("gemini-9.9-supernova", input_tokens=1000, output_tokens=1000)
        self.assertEqual(cost.total_usd, 0.0)
        self.assertIsInstance(cost, CostBreakdown)
        # An unknown model must still echo back the token counts it was given.
        self.assertEqual(cost.input_tokens, 1000)
        self.assertEqual(cost.output_tokens, 1000)

    def test_prefix_resolution_uses_base_model_pricing(self):
        # A dated/suffixed model id should resolve via prefix match.
        exact = gemini_cost("gemini-2.5-flash", 100_000, 10_000)
        suffixed = gemini_cost("gemini-2.5-flash-preview-04-2026", 100_000, 10_000)
        self.assertEqual(exact.total_usd, suffixed.total_usd)

    def test_dated_flash_lite_resolves_to_flash_lite_not_flash(self):
        # Regression: "gemini-2.5-flash-lite-*" also starts with the
        # "gemini-2.5-flash" prefix. The longest matching prefix must win, so a
        # dated flash-lite model must be billed at flash-lite rates, not the
        # ~3-6x more expensive flash rates.
        lite_exact = gemini_cost("gemini-2.5-flash-lite", 100_000, 10_000)
        lite_dated = gemini_cost("gemini-2.5-flash-lite-preview-2026", 100_000, 10_000)
        flash = gemini_cost("gemini-2.5-flash", 100_000, 10_000)
        self.assertEqual(lite_dated.total_usd, lite_exact.total_usd)
        self.assertLess(lite_dated.total_usd, flash.total_usd)

    def test_flash_lite_is_cheaper_than_flash(self):
        flash = gemini_cost("gemini-2.5-flash", 1_000_000, 1_000_000)
        lite = gemini_cost("gemini-2.5-flash-lite", 1_000_000, 1_000_000)
        self.assertLess(lite.total_usd, flash.total_usd)

    def test_breakdown_components_sum_to_total(self):
        cost = gemini_cost("gemini-2.5-pro", 50_000, 20_000, cached_tokens=10_000)
        self.assertAlmostEqual(
            cost.total_usd,
            round(cost.input_usd + cost.output_usd + cost.cached_usd, 6),
            places=6,
        )

    def test_cached_tokens_cannot_make_billable_input_negative(self):
        # cached >= input must clamp billable input at zero, never go negative.
        cost = gemini_cost("gemini-2.5-flash", input_tokens=1000, output_tokens=0, cached_tokens=5000)
        self.assertEqual(cost.input_usd, 0.0)
        self.assertGreaterEqual(cost.total_usd, 0.0)

    def test_breakdown_is_immutable(self):
        cost = gemini_cost("gemini-2.5-flash", 100, 100)
        with self.assertRaises(Exception):
            cost.total_usd = 9.99  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
