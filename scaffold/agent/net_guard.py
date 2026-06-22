"""
agent/net_guard.py - THIN SHIM over ``agentkit.sandbox.net_guard``.

The default-deny egress allowlist this file used to implement now lives in
agentkit (``agentkit.sandbox.net_guard``). The lab CONSUMES it instead of
duplicating it. agentkit's port note is explicit: it dropped the scaffold's
settings-bound ``assert_backends_allowed`` because agentkit injects backends
rather than reading a global ``settings`` object.

So this shim:
  * re-exports agentkit's primitives (``EgressBlocked``, ``allowed_hosts``,
    ``host_of``, ``is_allowed``, ``assert_allowed``), and
  * KEEPS the lab-only ``assert_backends_allowed(settings)`` - the startup check
    that validates every configured backend URL against the allowlist. This is
    the one piece that did NOT map to agentkit (it is settings-coupled), so it
    stays here as lab glue, built on agentkit's ``assert_allowed``.
"""

from __future__ import annotations

from typing import Any

# The real implementation - imported from agentkit, not duplicated.
from agentkit.sandbox.net_guard import (  # noqa: F401  (re-exported)
    EgressBlocked,
    allowed_hosts,
    assert_allowed,
    host_of,
    is_allowed,
)

__all__ = [
    "EgressBlocked",
    "allowed_hosts",
    "assert_allowed",
    "host_of",
    "is_allowed",
    "assert_backends_allowed",
]


def assert_backends_allowed(settings: Any) -> list[str]:
    """Validate every configured backend URL against the allowlist at startup.

    Lab-only glue (agentkit injects backends, so it has no equivalent). Checks
    the generation backends (oMLX, VibeProxy) and the embeddings backend; returns
    the list of validated URLs on success, raises ``EgressBlocked`` on the first
    off-allowlist URL. Call this before the agent makes any request: a config
    mutated to point a backend off-box is the classic exfiltration signature.
    """
    urls = [
        getattr(settings, "omlx_base_url", ""),
        getattr(settings, "vibeproxy_base_url", ""),
        getattr(settings, "embed_base_url", ""),
    ]
    checked: list[str] = []
    for url in urls:
        if not url:
            continue
        assert_allowed(url)  # agentkit's deterministic, LLM-non-overridable check
        checked.append(url)
    return checked


if __name__ == "__main__":
    # Loopback allowed; external blocked (delegates to agentkit).
    assert is_allowed("http://localhost:8000/v1")
    assert not is_allowed("http://attacker.example/v1")
    print("net_guard shim -> agentkit.sandbox.net_guard  (+ lab assert_backends_allowed)")
