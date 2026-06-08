"""Standard-library unittest coverage for geminilens.observer.GeminiObserver."""

import os
import sys
import tempfile
import time
import types
import unittest

_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, os.path.abspath(_SRC))

from geminilens.observer import GeminiObserver, ToolCall, Trace  # noqa: E402
from geminilens.store import TraceStore  # noqa: E402


class ObserverTraceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = TraceStore(os.path.join(self._tmp.name, "traces.jsonl"))
        self.obs = GeminiObserver(store=self.store)

    def tearDown(self):
        self._tmp.cleanup()

    def test_trace_records_latency_and_cost(self):
        with self.obs.trace("gemini-2.5-flash", prompt="hi") as tr:
            tr.input_tokens = 100
            tr.output_tokens = 50
            time.sleep(0.01)
        rec = self.store.recent()[-1]
        self.assertEqual(rec["input_tokens"], 100)
        self.assertEqual(rec["output_tokens"], 50)
        self.assertGreater(rec["latency_ms"], 0)
        self.assertGreater(rec["cost_usd"], 0)

    def test_default_tags_merge_with_call_tags(self):
        obs = GeminiObserver(store=self.store, default_tags={"env": "test"})
        with obs.trace("gemini-2.5-flash", agent="research") as tr:
            tr.output_tokens = 1
        rec = self.store.recent()[-1]
        self.assertEqual(rec["tags"], {"env": "test", "agent": "research"})

    def test_run_tool_captures_args_result_and_timing(self):
        with self.obs.trace("gemini-2.5-flash", prompt="q") as tr:
            result = self.obs.run_tool(tr, "add", lambda a, b: a + b, 2, 3)
        self.assertEqual(result, 5)
        rec = self.store.recent()[-1]
        self.assertEqual(len(rec["tool_calls"]), 1)
        self.assertEqual(rec["tool_calls"][0]["name"], "add")
        self.assertIsNone(rec["tool_calls"][0]["error"])
        self.assertGreaterEqual(rec["tool_calls"][0]["duration_ms"], 0)

    def test_run_tool_captures_error_and_reraises(self):
        def boom():
            raise ValueError("nope")

        with self.assertRaises(ValueError):
            with self.obs.trace("gemini-2.5-flash") as tr:
                self.obs.run_tool(tr, "boom", boom)

        rec = self.store.recent()[-1]
        self.assertTrue(rec["tool_calls"][0]["error"].startswith("ValueError"))
        self.assertTrue(rec["error"].startswith("ValueError"))

    def test_exception_in_trace_is_recorded_and_reraised(self):
        with self.assertRaises(RuntimeError):
            with self.obs.trace("gemini-2.5-flash"):
                raise RuntimeError("kaboom")
        rec = self.store.recent()[-1]
        self.assertTrue(rec["error"].startswith("RuntimeError"))

    def test_on_trace_callback_invoked(self):
        seen = []
        obs = GeminiObserver(store=self.store, on_trace=seen.append)
        with obs.trace("gemini-2.5-flash") as tr:
            tr.output_tokens = 10
        self.assertEqual(len(seen), 1)
        self.assertIsInstance(seen[0], Trace)

    def test_on_trace_callback_failure_does_not_break_agent(self):
        def explode(_tr):
            raise RuntimeError("exporter down")

        obs = GeminiObserver(store=self.store, on_trace=explode)
        # The observer must swallow exporter errors so it never breaks the agent.
        with obs.trace("gemini-2.5-flash") as tr:
            tr.output_tokens = 10
        self.assertEqual(len(self.store.recent()), 1)


class RecordResponseTests(unittest.TestCase):
    def setUp(self):
        self.obs = GeminiObserver(store=TraceStore())

    def _new_trace(self):
        return Trace(trace_id="t", model="gemini-2.5-flash", started_at=time.time())

    def test_record_response_genai_usage_metadata(self):
        usage = types.SimpleNamespace(
            prompt_token_count=120,
            candidates_token_count=42,
            cached_content_token_count=30,
        )
        response = types.SimpleNamespace(usage_metadata=usage, text="hello world")
        tr = self._new_trace()
        self.obs.record_response(tr, response)
        self.assertEqual(tr.input_tokens, 120)
        self.assertEqual(tr.output_tokens, 42)
        self.assertEqual(tr.cached_tokens, 30)
        self.assertEqual(tr.response, "hello world")

    def test_record_response_openai_dict_usage(self):
        response = types.SimpleNamespace(
            usage={"prompt_token_count": 7, "candidates_token_count": 3},
            text="ok",
        )
        tr = self._new_trace()
        self.obs.record_response(tr, response)
        self.assertEqual(tr.input_tokens, 7)
        self.assertEqual(tr.output_tokens, 3)

    def test_record_response_without_usage_is_noop_on_tokens(self):
        response = types.SimpleNamespace(text="just text")
        tr = self._new_trace()
        self.obs.record_response(tr, response)
        self.assertEqual(tr.input_tokens, 0)
        self.assertEqual(tr.response, "just text")


class TraceModelTests(unittest.TestCase):
    def test_to_dict_round_trips_tool_calls(self):
        tr = Trace(trace_id="x", model="gemini-2.5-flash", started_at=0.0)
        tr.tool_calls.append(ToolCall(name="t", args={}, result=1, duration_ms=1.0))
        d = tr.to_dict()
        self.assertEqual(d["trace_id"], "x")
        self.assertEqual(d["tool_calls"][0]["name"], "t")


if __name__ == "__main__":
    unittest.main()
