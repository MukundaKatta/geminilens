from geminilens.cost import gemini_cost


def test_flash_under_threshold():
    cost = gemini_cost("gemini-2.5-flash", input_tokens=1_000_000, output_tokens=500_000)
    # 1M input @ 0.30 + 500k output @ 2.50 = 0.30 + 1.25 = 1.55
    assert cost.input_usd == 0.30
    assert cost.output_usd == 1.25
    assert cost.total_usd == 1.55


def test_pro_over_threshold():
    cost = gemini_cost(
        "gemini-2.5-pro",
        input_tokens=200_000,
        output_tokens=10_000,
    )
    # Over 128k threshold: input 2.50, output 15.00 per 1M
    # 200k * 2.50 / 1M = 0.50, 10k * 15.00 / 1M = 0.15
    assert cost.input_usd == 0.50
    assert cost.output_usd == 0.15
    assert cost.total_usd == 0.65


def test_cached_input_discount():
    cost = gemini_cost(
        "gemini-2.5-flash",
        input_tokens=1_000_000,
        output_tokens=0,
        cached_tokens=500_000,
    )
    # 500k billable @ 0.30 + 500k cached @ 0.075 (=25% of 0.30)
    # = 0.15 + 0.0375 = 0.1875
    assert cost.input_usd == 0.15
    assert cost.cached_usd == 0.0375
    assert cost.total_usd == 0.1875


def test_unknown_model_returns_zero():
    cost = gemini_cost("gemini-9.9-supernova", input_tokens=1000, output_tokens=1000)
    assert cost.total_usd == 0.0
