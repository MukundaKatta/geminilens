"""Egress allowlist for agent tool calls. Wraps httpx.Client to enforce that
only approved domains can be reached from inside tool implementations."""

from __future__ import annotations

import urllib.parse
from collections.abc import Iterable

import httpx


class EgressBlocked(RuntimeError):
    """Raised when an agent tool attempts to reach a disallowed host."""


class EgressGuard:
    def __init__(self, allow: Iterable[str]):
        self._allow = {h.lower().lstrip(".") for h in allow}
        self._violations: list[str] = []

    def is_allowed(self, url: str) -> bool:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
        if not host:
            return False
        if host in self._allow:
            return True
        # Subdomain match: foo.example.com allowed if example.com on list
        for entry in self._allow:
            if host.endswith("." + entry):
                return True
        return False

    def violations(self) -> list[str]:
        return list(self._violations)

    def client(self, **httpx_kwargs) -> httpx.Client:
        """Return an httpx.Client that raises EgressBlocked on disallowed hosts."""
        guard = self

        class _GuardedTransport(httpx.HTTPTransport):
            def handle_request(self, request: httpx.Request) -> httpx.Response:
                if not guard.is_allowed(str(request.url)):
                    guard._violations.append(str(request.url))
                    raise EgressBlocked(f"egress to {request.url.host} blocked by allowlist")
                return super().handle_request(request)

        return httpx.Client(transport=_GuardedTransport(), **httpx_kwargs)
