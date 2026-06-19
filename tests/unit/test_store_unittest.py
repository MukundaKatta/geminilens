"""Standard-library unittest coverage for geminilens.store.TraceStore."""

import json
import os
import sys
import tempfile
import threading
import unittest

_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, os.path.abspath(_SRC))

from geminilens.store import TraceStore  # noqa: E402


class TraceStoreInMemoryTests(unittest.TestCase):
    def test_recent_returns_appended_records_in_order(self):
        store = TraceStore()  # in-memory only
        for i in range(5):
            store.append({"i": i})
        self.assertEqual([r["i"] for r in store.recent()], [0, 1, 2, 3, 4])

    def test_recent_respects_limit(self):
        store = TraceStore()
        for i in range(10):
            store.append({"i": i})
        last_three = store.recent(limit=3)
        self.assertEqual([r["i"] for r in last_three], [7, 8, 9])

    def test_ring_buffer_evicts_oldest(self):
        store = TraceStore(in_memory_cap=3)
        for i in range(6):
            store.append({"i": i})
        self.assertEqual([r["i"] for r in store.recent()], [3, 4, 5])

    def test_no_file_means_load_file_is_empty(self):
        store = TraceStore()
        self.assertEqual(list(store.load_file()), [])


class TraceStoreFileTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._tmp.name, "nested", "traces.jsonl")

    def tearDown(self):
        self._tmp.cleanup()

    def test_append_creates_parent_dir_and_persists_jsonl(self):
        store = TraceStore(self.path)
        store.append({"trace_id": "abc", "cost_usd": 0.5})
        store.append({"trace_id": "def", "cost_usd": 1.5})
        self.assertTrue(os.path.exists(self.path))
        loaded = list(store.load_file())
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0]["trace_id"], "abc")
        self.assertEqual(loaded[1]["cost_usd"], 1.5)

    def test_load_file_skips_blank_and_corrupt_lines(self):
        store = TraceStore(self.path)
        store.append({"ok": 1})
        with open(self.path, "a", encoding="utf-8") as f:
            f.write("\n")
            f.write("not json at all\n")
            f.write("   \n")
        store.append({"ok": 2})
        loaded = list(store.load_file())
        self.assertEqual([r["ok"] for r in loaded], [1, 2])

    def test_non_serializable_values_fall_back_to_str(self):
        store = TraceStore(self.path)
        # default=str means objects without native JSON support don't explode.
        store.append({"when": object()})
        with open(self.path, encoding="utf-8") as f:
            line = f.read().strip()
        record = json.loads(line)
        self.assertIn("when", record)
        self.assertIsInstance(record["when"], str)

    def test_concurrent_appends_are_all_recorded(self):
        store = TraceStore(self.path)

        def worker(start):
            for i in range(start, start + 50):
                store.append({"i": i})

        threads = [threading.Thread(target=worker, args=(s,)) for s in (0, 100, 200)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        loaded = list(store.load_file())
        self.assertEqual(len(loaded), 150)
        self.assertEqual({r["i"] for r in loaded}, set(range(50)) | set(range(100, 150)) | set(range(200, 250)))


if __name__ == "__main__":
    unittest.main()
