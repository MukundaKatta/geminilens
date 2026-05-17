from types import SimpleNamespace

from geminilens.azure import AzureObserver, azure_cost
from geminilens.store import TraceStore


def test_gpt4o_pricing():
    # 1M input @ 2.50 + 500k output @ 10.00 = 2.50 + 5.00 = 7.50
    assert azure_cost("gpt-4o", 1_000_000, 500_000) == 7.50


def test_gpt41_mini_pricing():
    # 1M in @ 0.40 + 1M out @ 1.60 = 2.00
    assert azure_cost("gpt-4.1-mini", 1_000_000, 1_000_000) == 2.00


def test_cached_discount():
    # 500k billable @ 2.50 = 1.25; 500k cached @ 1.25 = 0.625; output 0
    assert azure_cost("gpt-4o", 1_000_000, 0, cached_tokens=500_000) == 1.875


def test_unknown_model_zero():
    assert azure_cost("not-a-model", 1000, 1000) == 0.0


def test_observer_records_usage_and_cost(tmp_path):
    store = TraceStore(tmp_path / "az.jsonl")
    obs = AzureObserver(store=store)

    fake_response = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=1000,
            completion_tokens=500,
            prompt_tokens_details=SimpleNamespace(cached_tokens=200),
        ),
        choices=[SimpleNamespace(message=SimpleNamespace(content="hi from azure"))],
    )

    with obs.trace("gpt-4o", prompt="q") as tr:
        obs.record_response(tr, fake_response)

    rec = store.recent()[-1]
    assert rec["input_tokens"] == 1000
    assert rec["output_tokens"] == 500
    assert rec["cached_tokens"] == 200
    assert rec["response"] == "hi from azure"
    assert rec["cost_usd"] > 0
