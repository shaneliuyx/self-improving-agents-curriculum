"""
evals/behavior_test.py - behavior regression guard.

Most tests check that code COMPILES. This checks that the agent actually
*behaves* correctly. It has two tiers:

  BACKEND-INDEPENDENT (run always, including in CI - no LLM call):
    - verify gate: ACCEPT a real improvement, REJECT a regression, REJECT a
      malformed proposal. This is the keep/discard DECISION logic (Module 07).
    - skill persistence: a Skill round-trips through save -> load -> list.

  BACKEND-DEPENDENT (run only against REACHABLE backends):
    - tool USE: the agent runs the calculator and returns 396 (native tool_calls
      on Claude; text-tool-call fallback on oMLX).
    - embeddings: MemoryStore embeds locally and ranks the right memory.
    - reflection: a trajectory -> structured Lessons (Module 05).
    - skill propose: a trajectory -> a Skill proposal without error (Module 06).
    - skill search: semantic retrieval finds a saved skill (Module 06).
    - DGM evolve discard: a worse variant is REJECTED by the gate (Module 08).

Backends that are down are SKIPPED, so this is safe in CI (the independent tier
still runs and asserts real behavior; the dependent tier skips). It only FAILS
on a genuine behavior regression.

Run locally (with a backend up):
    OMLX_API_KEY=... OMLX_MODEL=Qwen2.5-Coder-7B-Instruct-4bit \
    EMBED_MODEL=nomicai-modernbert-embed-base-bf16 \
    VIBE_MODEL=claude-sonnet-4-5-20250929 \
    python -m evals.behavior_test

Exit codes: 0 = all run checks passed; 1 = a failure.
"""

from __future__ import annotations

import pathlib
import socket
import sys
import tempfile


def _reachable(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout):
            return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Backend-INDEPENDENT checks (no LLM call - run even in CI)
# ---------------------------------------------------------------------------

def _check_verify_gate() -> tuple[bool, str]:
    """The gate ACCEPTs a real improvement, REJECTs a regression and a bad proposal."""
    from verification.gates import VerdictStatus, verify

    good = verify({"type": "prompt", "content": "x"}, candidate_score=0.8,
                  baseline_score=0.5, run_safety_check=False)
    regr = verify({"type": "prompt", "content": "x"}, candidate_score=0.4,
                  baseline_score=0.5, run_safety_check=False)
    bad = verify({}, candidate_score=0.8, baseline_score=0.5, run_safety_check=False)

    ok = (good.accepted
          and regr.status == VerdictStatus.REJECT
          and bad.status == VerdictStatus.REJECT)
    return ok, f"improve={good.status.value} regression={regr.status.value} malformed={bad.status.value}"


def _check_edit_recover() -> tuple[bool, str]:
    """The write->verify->recover chain (Stage 4 / the article's flagship):
    edit_file applies a unique anchored edit atomically and returns a snapshot;
    an ambiguous anchor is refused; and a write to a capability-scoped dir
    (verification/) is denied BY PATH before the file is even read. No LLM."""
    import agent.tools as t

    root = t._PROJECT_ROOT.resolve()
    p = root / "outputs" / "_behaviortest_edit.py"
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.write_text("def add(a, b):\n    return a - b  # bug\n")
        good = t._tool_edit_file("outputs/_behaviortest_edit.py", "a - b", "a + b")
        applied = good.get("ok") and "a + b" in p.read_text() and "a - b" in good.get("snapshot", "")
        p.write_text("dup\ndup\n")
        ambiguous = "ambiguous" in t._tool_edit_file("outputs/_behaviortest_edit.py", "dup", "x").get("error", "")
        denied = "denied" in t._tool_edit_file("verification/gates.py", "def verify", "def hacked").get("error", "").lower()
    finally:
        p.unlink(missing_ok=True)
    ok = bool(applied and ambiguous and denied)
    return ok, f"apply+snapshot={bool(applied)} ambiguous-refused={ambiguous} forbidden-denied={denied}"


def _check_skill_persist() -> tuple[bool, str]:
    """A Skill round-trips through save -> load -> list (uses a temp skills dir)."""
    from config import settings
    from skills.library import Skill, list_skills, load_skill, save_skill

    settings.skills_dir = pathlib.Path(tempfile.mkdtemp())  # isolate from the real library
    sk = Skill(
        name="use_calculator",
        description="Use the calculator tool for any arithmetic.",
        trigger="when the task requires arithmetic computation",
        steps=["call the calculator tool with the expression", "return its result"],
        eval_score=0.9,
        source_task="17 * 23 + 5",
    )
    save_skill(sk)
    loaded = load_skill("use_calculator")
    ok = (loaded is not None and loaded.name == "use_calculator"
          and loaded.steps == sk.steps and "use_calculator" in list_skills())
    return ok, f"loaded={(loaded.name if loaded else None)!r} list={list_skills()}"


# ---------------------------------------------------------------------------
# Backend-DEPENDENT checks
# ---------------------------------------------------------------------------

def _check_tool_use(backend: str) -> tuple[bool, str]:
    """The agent executes the calculator tool and answers 396."""
    from agent.loop import run_agent

    r = run_agent("What is 17 * 23 + 5? Use the calculator tool.", max_rounds=5, backend=backend)
    tool_ran = any(s.role == "tool" and s.tool_name == "calculator" for s in r.trajectory)
    correct = "396" in (r.answer or "")
    return (tool_ran and correct), f"tool_ran={tool_ran} has_396={correct} stop={r.stop_reason}"


def _check_embeddings() -> tuple[bool, str]:
    """MemoryStore embeds locally (oMLX) and ranks the right memory first."""
    from memory.store import MemoryStore

    ms = MemoryStore(db_path=pathlib.Path(tempfile.mktemp(suffix=".db")))
    try:
        ms.add("semantic", "Use a small local model for cheap classification steps.")
        ms.add("semantic", "Sandboxes contain the blast radius of self-modification.")
        hits = ms.search("how should I route cheap classification steps?", top_k=1)
    finally:
        ms.close()
    ok = bool(hits) and "cheap" in hits[0].content.lower()
    return ok, f"top_hit={(hits[0].content[:44] if hits else None)!r}"


def _check_memory_injection() -> tuple[bool, str]:
    """The READ side of the experience layer: a stored lesson is retrieved and
    formatted into an injectable <memory_context> block, and an empty store
    degrades to an empty string (never breaks the loop). Guards the write-only
    gap that Stage 3 closed - reflection writes lessons the loop must read back."""
    from memory.store import MemoryStore

    ms = MemoryStore(db_path=pathlib.Path(tempfile.mktemp(suffix=".db")))
    try:
        empty = ms.inject_context("anything")          # no memories yet
        ms.add("semantic", "Always use the calculator tool for arithmetic.")
        ctx = ms.inject_context("how do I add two numbers")
    finally:
        ms.close()
    ok = (empty == "") and ("<memory_context>" in ctx) and ("calculator" in ctx.lower())
    return ok, f"empty={empty!r} injected={'<memory_context>' in ctx}"


def _check_reflection(backend: str) -> tuple[bool, str]:
    """A completed trajectory produces structured Lessons via the LLM."""
    from agent.loop import run_agent
    from reflection.reflect import Lessons, reflect_on_trajectory

    r = run_agent("What is 12 + 30? Use the calculator tool.", max_rounds=4, backend=backend)
    lessons = reflect_on_trajectory(r, save_to_memory=False)
    ok = (isinstance(lessons, Lessons) and bool(lessons.raw_response)
          and isinstance(lessons.confidence, float) and bool(lessons.heuristic))
    return ok, f"heuristic={lessons.heuristic[:40]!r} conf={lessons.confidence}"


def _check_skill_propose(backend: str) -> tuple[bool, str]:
    """propose_skill runs over a real trajectory and returns a Skill (or None) cleanly."""
    from agent.loop import run_agent
    from skills.library import Skill, propose_skill

    r = run_agent("What is 9 * 9? Use the calculator tool.", max_rounds=4, backend=backend)
    summary = (f"Task: {r.task}\nAnswer: {r.answer}\n"
               f"Tools: {[(s.tool_name, s.tool_result) for s in r.trajectory if s.role == 'tool']}")
    sk = propose_skill(summary, source_task=r.task)
    ok = sk is None or (isinstance(sk, Skill) and bool(sk.name) and isinstance(sk.steps, list))
    return ok, f"proposed={(sk.name if sk else None)!r}"


def _check_skill_search() -> tuple[bool, str]:
    """Semantic skill retrieval finds the calculator skill saved by _check_skill_persist."""
    from skills.library import search_skills

    hits = search_skills("I need to do an arithmetic calculation", top_k=3)
    ok = any(s.name == "use_calculator" for s in hits)
    return ok, f"found={[s.name for s in hits]}"


def _check_evolve_discard() -> tuple[bool, str]:
    """A worse variant (fake low eval score) is REJECTED by the keep/discard gate."""
    from config import settings
    from evolve.loop import EvolutionResult, run_evolution_step

    settings.evolve_archive_dir = pathlib.Path(tempfile.mkdtemp())  # isolate the archive
    res = run_evolution_step(
        baseline_prompt="You are a helpful agent. Use tools when needed.",
        baseline_score=0.5,
        eval_fn=lambda _prompt: 0.1,   # candidate scores worse than baseline
    )
    ok = isinstance(res, EvolutionResult) and res.accepted is False
    return ok, f"accepted={res.accepted} reason={res.verdict_reason[:48]!r}"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main() -> int:
    results: list[tuple[str, bool, str]] = []

    # --- always-on (CI-safe, no backend) ---
    results.append(("verify-gate logic", *_check_verify_gate()))
    results.append(("write-verify-recover chain", *_check_edit_recover()))
    results.append(("skill persist+retrieve", *_check_skill_persist()))

    omlx_up = _reachable("localhost", 8000)
    vibe_up = _reachable("localhost", 8317)

    if omlx_up:
        results.append(("oMLX tool-use", *_check_tool_use("omlx")))
        results.append(("oMLX embeddings", *_check_embeddings()))
        results.append(("memory injection (read-side)", *_check_memory_injection()))
        results.append(("reflection pipeline", *_check_reflection("omlx")))
        results.append(("skill propose", *_check_skill_propose("omlx")))
        results.append(("skill search (embeddings)", *_check_skill_search()))
        results.append(("DGM evolve discard", *_check_evolve_discard()))
    else:
        print("skip: oMLX :8000 not reachable (tool-use/embeddings/reflection/skill/evolve)")

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
        print(f"\n{failed} of {len(results)} behavior check(s) FAILED")
        return 1
    print(f"\nAll {len(results)} behavior check(s) PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
