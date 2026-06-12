"""
verification/try_gate.py - hands-on demo of the verification gate (Module 07).

Runs the real `verify()` gate on three proposals to show its three outcomes:
  ACCEPT   - a contained change that improves on the baseline,
  REJECT   - a change that does not beat the baseline (regression gate),
  ESCALATE - a change that touches a sandboxed capability (containment gate).

Run from the scaffold root:
  AGENT_BACKEND=omlx     python verification/try_gate.py
  AGENT_BACKEND=vibeproxy JUDGE_BACKEND=vibeproxy python verification/try_gate.py

`run_safety_check=False` keeps this demo deterministic and offline (the syntax,
containment, and regression gates are all deterministic). Flip it to True to also
run the LLM safety judge through whichever backend AGENT_BACKEND selects.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from verification.gates import verify


def _show(label: str, verdict) -> None:
    print(f"--- {label} ---")
    print(f"{verdict.status.value}: {verdict.reason} (accepted={verdict.accepted})\n")


def main() -> None:
    # 1. Good proposal: contained, and it improves on the baseline -> ACCEPT.
    good = {
        "type": "prompt",
        "content": "When the user asks for file diffs, always include surrounding context lines.",
        "note": "add diff-context instruction",
    }
    _show("Good proposal (improves, contained)",
          verify(good, candidate_score=0.90, baseline_score=0.60, run_safety_check=False))

    # 2. No-op proposal: ties the baseline -> REJECT (strictly-better required).
    noop = {"type": "prompt", "content": "Reword one sentence with no behavioural change.", "note": "noop"}
    _show("No-op proposal (no improvement)",
          verify(noop, candidate_score=0.60, baseline_score=0.60, run_safety_check=False))

    # 3. Capability-touching proposal: trips the containment gate -> ESCALATE.
    unsafe = {
        "type": "skill",
        "content": "import os, subprocess; subprocess.run(cmd); os.remove(path); eval(expr)",
        "note": "auto-cleanup helper",
    }
    _show("Unsafe proposal (needs sandbox)",
          verify(unsafe, candidate_score=0.90, baseline_score=0.60, run_safety_check=False))


if __name__ == "__main__":
    main()
