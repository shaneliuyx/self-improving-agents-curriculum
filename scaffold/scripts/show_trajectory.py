"""
scripts/show_trajectory.py - print an agent trajectory step by step (Module 03).

Demonstrates "trajectory capture" - the architectural seam that RECORD and
REFLECT read from. Run from the scaffold root:

  AGENT_BACKEND=omlx     python scripts/show_trajectory.py "What is 6 * 7?"
  AGENT_BACKEND=vibeproxy python scripts/show_trajectory.py "Summarise GOAL.md"
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.loop import run_agent


def main() -> None:
    task = " ".join(sys.argv[1:]) or "Read the file GOAL.md and summarise it in one sentence."
    result = run_agent(task, log=False)

    for i, step in enumerate(result.trajectory):
        content = str(step.content)[:200]
        print(f"[{i}] {step.role}: {content}")
        if step.tool_name:
            meta = {
                "tool_name": step.tool_name,
                "tool_args": step.tool_args,
                "tool_result": step.tool_result,
            }
            print(f"     META: {json.dumps(meta, indent=2)}")

    print(f"\n[stop] {result.stop_reason} | rounds={result.rounds_used} | success={result.success}")


if __name__ == "__main__":
    main()
