"""Standard-library unittest coverage for geminilens.azure."""

import os
import sys
import time
import types
import unittest

_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, os.path.abspath(_SRC))

from geminilens.azure import AzureObserver, azure_cost  # noqa: E402
from geminilens.observer import Trace  # noqa: E402
from geminilens.store import TraceStore  # noqa: E402


class AzureCostTests(unittest.TestCase):
    def test_known_model_cost(self):
        # gpt-4o: 2.50 input / 10.00 output per 1M.
        cost = azure_cost("gpt-4o", input_tokens=1_000_000, output_tokens=1_000_000)
        self.assertEqual(cost, round(2.50 + 10.00, 6))

    def test_cached_tokens_use_cache_rate(self):
        # gpt-4o cached rate is 1.25; 1M cached + 0 fresh input + 0 output.
        cost = azure_cost("gpt-4o", input_tokens=1_000_000, output_tokens=0, cached_tokens=1_000_000)
        self.assertEqual(cost, 1.25)

    def test_unknown_model_is_zero(self):
        self.assertEqual(azure_cost("totally-made-up", 1000, 1000), 0.0)

    def test_prefix_match(self):
        a = azure_cost("gpt-4o-mini", 100_000, 10_000)
        b = azure_cost("gpt-4o-mini-2026-01-01", 100_000, 10_000)
        self.assertEqual(a, b)

    def test_dated_mini_resolves_to_mini_not_full(self):
        # Regression: "gpt-4o-mini-*" also starts with the "gpt-4o" prefix.
        # The longest matching prefix must win so a mini deployment is billed at
        # mini rates, not the ~16x more expensive gpt-4o rates.
        mini = azure_cost("gpt-4o-mini-2026-01-01", 1_000_000, 0)
        full = azure_cost("gpt-4o", 1_000_000, 0)
        self.assertEqual(mini, 0.15)
        self.assertLess(mini, full)

    def test_cached_never_makes_input_negative(self):
        cost = azure_cost("gpt-4o", input_tokens=1000, output_tokens=0, cached_tokens=99999)
        self.assertGreaterEqual(cost, 0.0)


class AzureObserverTests(unittest.TestCase):
    def test_trace_uses_azure_pricing(self):
        store = TraceStore()
        obs = AzureObserver(store=store)
        with obs.trace("gpt-4o-mini", prompt="hi") as tr:
            tr.input_tokens = 1_000_000
            tr.output_tokens = 0
        rec = store.recent()[-1]
        # gpt-4o-mini input rate is 0.15 per 1M.
        self.assertEqual(rec["cost_usd"], 0.15)

    def test_record_response_parses_openai_shape(self):
        obs = AzureObserver(store=TraceStore())
        usage = types.SimpleNamespace(
            prompt_tokens=11,
            completion_tokens=4,
            prompt_tokens_details=types.SimpleNamespace(cached_tokens=5),
        )
        message = types.SimpleNamespace(content="the answer")
        choice = types.SimpleNamespace(message=message)
        response = types.SimpleNamespace(usage=usage, choices=[choice])
        tr = Trace(trace_id="t", model="gpt-4o-mini", started_at=time.time())
        obs.record_response(tr, response)
        self.assertEqual(tr.input_tokens, 11)
        self.assertEqual(tr.output_tokens, 4)
        self.assertEqual(tr.cached_tokens, 5)
        self.assertEqual(tr.response, "the answer")


if __name__ == "__main__":
    unittest.main()
