import pytest

from geminilens.guard import EgressGuard, EgressBlocked


def test_allow_exact_host():
    g = EgressGuard(allow=["en.wikipedia.org"])
    assert g.is_allowed("https://en.wikipedia.org/wiki/Gemini")


def test_allow_subdomain():
    g = EgressGuard(allow=["wikipedia.org"])
    assert g.is_allowed("https://en.wikipedia.org/wiki/Gemini")


def test_block_unknown_host():
    g = EgressGuard(allow=["wikipedia.org"])
    assert not g.is_allowed("https://evil.example.com/x")


def test_client_blocks_disallowed(monkeypatch):
    g = EgressGuard(allow=["wikipedia.org"])
    client = g.client()
    with pytest.raises(EgressBlocked):
        client.get("https://evil.example.com/exfil")
    assert len(g.violations()) == 1
    assert "evil.example.com" in g.violations()[0]
