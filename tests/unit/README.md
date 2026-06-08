# Dependency-free unit tests

These tests exercise the pure-Python core of GeminiLens (cost accounting,
drift detection, the JSONL trace store, the observer and the Azure adapter)
using only the Python standard library. They require **no third-party
packages** and no GCP/Azure credentials, so they run anywhere Python 3.10+ is
available:

```bash
python3 -m unittest discover -s tests/unit
```

The egress guard (`geminilens.guard`) and the exporters depend on `httpx` and
other optional packages; those are covered by the `pytest` suite in the parent
`tests/` directory:

```bash
pip install -e ".[dev,exporters]"
PYTHONPATH=src pytest -q
```
