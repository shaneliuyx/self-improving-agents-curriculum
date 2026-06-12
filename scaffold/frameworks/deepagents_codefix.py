"""
frameworks/deepagents_codefix.py
A self-improving code-fix agent on deepagents, backend-swappable to oMLX/VibeProxy.

Contrast with the hand-built agent/loop.py: the loop, file edits, and
checkpointing are the framework's; the run_tests tool and the external eval
gate (deepagents_cycle.py) are still ours.

Install:  pip install -e ".[frameworks]"   # installs deepagents + langchain-openai
Run:
  AGENT_BACKEND=omlx      python -m frameworks.deepagents_codefix
  AGENT_BACKEND=vibeproxy python -m frameworks.deepagents_codefix

deepagents is an optional dep; this module imports cleanly even when absent.
The RuntimeError is raised only when create_deep_agent() is actually called.
"""

from __future__ import annotations

import subprocess

try:
    from deepagents import create_deep_agent  # type: ignore
    _DEEPAGENTS_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dep
    _DEEPAGENTS_AVAILABLE = False
    create_deep_agent = None  # type: ignore

from frameworks.deepagents_backend import make_model


def run_tests(test_path: str) -> str:
    """Run pytest on a path; return pass/fail + captured output.
    This is OUR domain tool - the framework supplies file edit + shell, but
    'what counts as success' is ours to define (see the eval-gate note below)."""
    proc = subprocess.run(
        ["python", "-m", "pytest", test_path, "-x", "-q"],
        capture_output=True, text=True, timeout=120,
    )
    status = "PASS" if proc.returncode == 0 else "FAIL"
    return f"[{status}]\n{proc.stdout[-2000:]}\n{proc.stderr[-1000:]}"


SYSTEM = """You are a code-fix agent. Given a failing test:
1. Read the test and the source file it exercises (use the filesystem tools).
2. Make the SMALLEST edit to the source that could fix the failure.
3. Call run_tests to check. If it still fails, read the new output and try again.
4. Stop when the test passes, or after 5 edit-test cycles. Do not edit the test itself."""


def _build_agent():
    """Build and return the deepagents agent. Raises RuntimeError if deepagents
    is not installed."""
    if not _DEEPAGENTS_AVAILABLE:  # pragma: no cover
        raise RuntimeError(
            "deepagents is not installed.\n"
            "Run:  pip install -e \".[frameworks]\"\n"
            "(this installs the optional 'deepagents' package)."
        )
    return create_deep_agent(
        model=make_model(),          # <-- oMLX/VibeProxy via base_url (section 2)
        tools=[run_tests],           # <-- our domain tool; file edit/shell are built in
        system_prompt=SYSTEM,
    )


# Module-level agent — constructed lazily on first real import to avoid
# raising ImportError at import time when deepagents is absent.
_agent = None


def get_agent():
    """Return the singleton agent, building it on first call."""
    global _agent
    if _agent is None:
        _agent = _build_agent()
    return _agent


# Convenience alias: agent is None until get_agent() is called.
# deepagents_cycle.py uses get_agent() directly.
agent = None


if __name__ == "__main__":
    result = get_agent().invoke({"messages": "Fix the failing test in tests/test_buggy.py"})
    print(result["messages"][-1].content)
