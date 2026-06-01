"""
agent/net_guard.py - Network egress allowlist (containment primitive).

THREAT (specific to a self-improving agent): the agent can propose changes to
its own config. One bad prompt-mutation proposal that rewrites a backend
`base_url` from `localhost:8000` to `http://attacker.example/v1` turns every
subsequent turn into an exfiltration channel - it ships the full prompt (and any
API key in the Authorization header) off-box, and the agent never "looks"
malicious because it is just calling its LLM as usual.

DEFENSE: an explicit allowlist of hosts the agent is permitted to talk to. The
only legitimate egress targets are the local oMLX (:8000) and VibeProxy (:8317)
backends, all on the loopback interface. `assert_backends_allowed()` validates
the configured backend URLs at startup and refuses to run if any points off the
allowlist - so a mutated config is caught before the first request, not after
the data has already left.

This is the L2 deterministic counterpart to Module 09's sandbox: the sandbox
contains what a skill can *do* locally; net_guard contains where the process can
*reach* over the network. Both are non-overridable by the LLM.

No external deps. Pure stdlib (urllib.parse for host extraction).
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse


class EgressBlocked(Exception):
    """Raised when a URL/host is not on the egress allowlist."""


# Loopback is always allowed - the local backends live here. Anything else must
# be opted in explicitly via ALLOWED_EGRESS_HOSTS (comma-separated hostnames).
_DEFAULT_ALLOWED = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def allowed_hosts() -> set[str]:
    """The current egress allowlist: loopback plus any ALLOWED_EGRESS_HOSTS."""
    extra = os.getenv("ALLOWED_EGRESS_HOSTS", "")
    extras = {h.strip().lower() for h in extra.split(",") if h.strip()}
    return _DEFAULT_ALLOWED | extras


def host_of(url: str) -> str:
    """Extract the lowercased hostname from a URL. A bare host (no scheme) is
    returned as-is so callers can pass either a full URL or a hostname."""
    parsed = urlparse(url if "://" in url else f"//{url}", scheme="")
    return (parsed.hostname or url).lower()


def is_allowed(url: str) -> bool:
    """True if `url`'s host is on the egress allowlist."""
    return host_of(url) in allowed_hosts()


def assert_allowed(url: str) -> None:
    """Raise EgressBlocked if `url`'s host is not on the allowlist."""
    if not is_allowed(url):
        raise EgressBlocked(
            f"egress blocked: host {host_of(url)!r} (from {url!r}) is not on the "
            f"allowlist {sorted(allowed_hosts())}. If this is intentional, add it "
            f"to ALLOWED_EGRESS_HOSTS - but a backend URL that left loopback is "
            f"the classic config-mutation exfiltration signature."
        )


def assert_backends_allowed(settings: Any) -> list[str]:
    """Validate every configured backend URL against the allowlist at startup.

    Checks the generation backends (oMLX, VibeProxy) and the embeddings backend.
    Returns the list of validated URLs on success; raises EgressBlocked on the
    first off-allowlist URL. Call this before the agent makes any request.
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
        assert_allowed(url)
        checked.append(url)
    return checked
