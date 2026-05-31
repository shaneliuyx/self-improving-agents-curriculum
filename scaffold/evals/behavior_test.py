"""
evals/behavior_test.py - behavior regression guard.

Most tests check that code COMPILES. This checks that the agent actually
*behaves* correctly against whatever backends are reachable:
  - tool USE: the agent runs the calculator tool and returns 396 (not the raw
    tool-call text). This guards the native tool_calls path (VibeProxy/Claude)
    AND the text-tool-call fallback in agent/loop.py (oMLX small models).
  - embeddings: MemoryStore can embed locally and rank the right memory first.

Backends that are not running are SKIPPED, so this is safe to run in CI (where
nothing is reachable - it just prints SKIP and exits 0). It only FAILS when a
reachable backend produces wrong behavior - i.e. a genuine regression.

Run locally (with a backend up):
    OMLX_API_KEY=... OMLX_MODEL=Qwen2.5-Coder-7B-Instruct-4bit \
    EMBED_MODEL=nomicai-modernbert-embed-base-bf16 \
    VIBE_MODEL=claude-sonnet-4-5-20250929 \
    python -m evals.behavior_test

Exit codes: 0 = all reachable backends passed (or none reachable); 1 = a failure.
"""

from __future__ import annotations

import socket
import sys


def _reachable(host: str, port: int, timeout: float = 1.0) -> bool:
    """True if a TCP connection to host:port succeeds quickly."""
    try:
        with socket.create_connection((host, port), timeout):
            return True
    except OSError:
        return False


def _check_tool_use(backend: str) -> tuple[bool, str]:
    """Assert the agent executes the calculator tool and answers 396."""
    from agent.loop import run_agent

    r = run_agent(
        "What is 17 * 23 + 5? Use the calculator tool.",
        max_rounds=5,
        backend=backend,
    )
    tool_ran = any(s.role == "tool" and s.tool_name == "calculator" for s in r.trajectory)
    correct = "396" in (r.answer or "")
    detail = f"tool_ran={tool_ran} answer_has_396={correct} stop={r.stop_reason} rounds={r.rounds_used}"
    return (tool_ran and correct), detail


def _check_embeddings() -> tuple[bool, str]:
    """Assert MemoryStore embeds locally (oMLX) and ranks the right memory first."""
    import pathlib
    import tempfile

    from memory.store import MemoryStore

    ms = MemoryStore(db_path=pathlib.Path(tempfile.mktemp(suffix=".db")))
    try:
        ms.add("semantic", "Use a small local model for cheap classification steps.")
        ms.add("semantic", "Sandboxes contain the blast radius of self-modification.")
        hits = ms.search("how should I route cheap classification steps?", top_k=1)
    finally:
        ms.close()
    ok = bool(hits) and "cheap" in hits[0].content.lower()
    return ok, f"top_hit={(hits[0].content[:48] if hits else None)!r}"


def main() -> int:
    omlx_up = _reachable("localhost", 8000)
    vibe_up = _reachable("localhost", 8317)

    if not omlx_up and not vibe_up:
        print("SKIP: no backend reachable (oMLX :8000 / VibeProxy :8317). Nothing to verify.")
        return 0

    results: list[tuple[str, bool, str]] = []

    if omlx_up:
        results.append(("oMLX tool-use", *_check_tool_use("omlx")))
        results.append(("oMLX embeddings", *_check_embeddings()))
    else:
        print("skip: oMLX :8000 not reachable")

    if vibe_up:
        results.append(("VibeProxy tool-use", *_check_tool_use("vibeproxy")))
    else:
        print("skip: VibeProxy :8317 not reachable")

    print("\n=== behavior eval ===")
    failed = 0
    for name, ok, detail in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
        failed += 0 if ok else 1

    if failed:
        print(f"\n{failed} behavior check(s) FAILED")
        return 1
    print(f"\nAll {len(results)} reachable-backend behavior check(s) PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
