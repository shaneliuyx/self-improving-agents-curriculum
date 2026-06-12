"""
frameworks/deepagents_cycle.py - framework runs the loop; WE gate the result.

This is the curriculum's non-negotiable: a self-improving agent must NOT
evaluate its own proposals.  deepagents runs the edit-test loop; run_eval is
the external, deterministic judge that decides keep-vs-discard.

See Module 11 §4.1 and the primitive->framework table in note 14 §3:
  "evals/run.py external eval gate" -> YOU (not the framework).

Install:  pip install -e ".[frameworks]"
Run:      python -m frameworks.deepagents_cycle
"""

from __future__ import annotations

try:
    from evals.run import run_eval  # the same deterministic judge from Module 10
    _EVALS_AVAILABLE = True
except ImportError:  # pragma: no cover - evals module may not exist yet
    _EVALS_AVAILABLE = False
    run_eval = None  # type: ignore

from frameworks.deepagents_codefix import get_agent


def one_cycle(task_msg: str) -> bool:
    """
    Run one fix cycle:
      1. deepagents agent edits + tests in its loop (framework's job).
      2. run_eval produces an external ground-truth report (our job).
      3. Accept iff no regressions and success_rate >= baseline.

    Returns True if the fix was accepted, False if it should be reverted.

    Raises RuntimeError if deepagents or evals.run are not available.
    """
    if not _EVALS_AVAILABLE:  # pragma: no cover
        raise RuntimeError(
            "evals.run is not available.\n"
            "Build the evals module first (Module 10 in the curriculum).\n"
            "Run:  pip install -e \".[frameworks]\""
        )

    get_agent().invoke({"messages": task_msg})         # framework: edit + test loop
    report = run_eval("post-deepagents-fix")           # OURS: external ground truth
    accepted = report.regression_count == 0 and report.success_rate >= report.baseline_rate
    # keep the edit on accept; git revert on reject (Module 08 discipline, unchanged)
    return accepted


if __name__ == "__main__":
    task = "Fix the failing test in tests/test_buggy.py"
    accepted = one_cycle(task)
    print("Fix accepted." if accepted else "Fix REJECTED - revert.")
