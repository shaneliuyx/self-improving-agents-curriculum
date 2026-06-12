"""
frameworks/deepagents_cycle.py - framework runs the loop; WE gate the result.

This is the curriculum's non-negotiable: a self-improving agent must NOT
evaluate its own proposals. deepagents runs the edit-test loop (it has its own
run_tests tool); `one_cycle` then re-runs the test suite INDEPENDENTLY as the
external, deterministic judge that decides keep-vs-discard. The agent's own
tool calls do not count - only our out-of-band pytest run does.

See Module 11 §4.1 and the primitive->framework table in note 14 §3:
  "evals/run.py external eval gate" -> YOU (not the framework).

Install:  pip install -e ".[frameworks]"   # installs deepagents + langchain-openai
Run:      python -m frameworks.deepagents_cycle
"""

from __future__ import annotations

import subprocess
import sys

from frameworks.deepagents_codefix import get_agent

TEST_PATH = "tests/test_buggy.py"


def _suite_passes(test_path: str = TEST_PATH) -> bool:
    """Independent ground truth: re-run the test suite ourselves and report pass/fail.

    Deliberately separate from the agent's own `run_tests` tool - the gate must
    not trust the agent's self-report.
    """
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", test_path, "-q"],
        capture_output=True, text=True, timeout=120,
    )
    return proc.returncode == 0


def one_cycle(task_msg: str, test_path: str = TEST_PATH) -> bool:
    """
    Run one fix cycle:
      1. deepagents agent edits + tests in its loop (framework's job).
      2. We re-run the suite out-of-band (our job) as ground truth.
      3. Accept iff the suite now passes.

    Returns True if the fix was accepted, False if it should be reverted.
    Raises RuntimeError if deepagents is not installed (via get_agent()).
    """
    before = _suite_passes(test_path)
    get_agent().invoke({"messages": task_msg})   # framework: edit + test loop
    after = _suite_passes(test_path)              # OURS: independent ground truth
    print(f"[gate] suite passed before={before} after={after}")
    return after


if __name__ == "__main__":
    task = f"Fix the failing test in {TEST_PATH} by editing the source under src/, not the test."
    accepted = one_cycle(task)
    print("Fix accepted (suite passes)." if accepted else "Fix REJECTED - suite still failing; revert.")
