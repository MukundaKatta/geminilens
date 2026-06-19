"""Verify the top-level package imports cleanly without optional dependencies.

The egress guard depends on ``httpx``; the rest of the library is pure
standard library. Importing ``geminilens`` (and using cost/drift/store/observer)
must therefore work even when ``httpx`` is not installed, with the guard only
pulling ``httpx`` in on first access.
"""

import importlib
import os
import sys
import unittest

_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, os.path.abspath(_SRC))


class PackageImportTests(unittest.TestCase):
    def test_top_level_import_exposes_core_api(self):
        geminilens = importlib.import_module("geminilens")
        for name in (
            "GeminiObserver",
            "Trace",
            "ToolCall",
            "TraceStore",
            "CostBreakdown",
            "gemini_cost",
            "DriftReport",
            "compute_drift",
        ):
            self.assertTrue(hasattr(geminilens, name), f"missing public name {name!r}")

    def test_version_matches_pyproject(self):
        geminilens = importlib.import_module("geminilens")
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        with open(os.path.join(root, "pyproject.toml"), encoding="utf-8") as f:
            pyproject = f.read()
        # Find the project version line.
        version = None
        for line in pyproject.splitlines():
            stripped = line.strip()
            if stripped.startswith("version"):
                version = stripped.split("=", 1)[1].strip().strip('"').strip("'")
                break
        self.assertIsNotNone(version, "could not find version in pyproject.toml")
        self.assertEqual(geminilens.__version__, version)

    def test_lazy_names_are_advertised_in_dir(self):
        geminilens = importlib.import_module("geminilens")
        self.assertIn("EgressGuard", dir(geminilens))
        self.assertIn("EgressBlocked", dir(geminilens))

    def test_unknown_attribute_raises_attribute_error(self):
        geminilens = importlib.import_module("geminilens")
        with self.assertRaises(AttributeError):
            geminilens.does_not_exist


if __name__ == "__main__":
    unittest.main()
