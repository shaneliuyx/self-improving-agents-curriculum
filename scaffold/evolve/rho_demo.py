"""
evolve/rho_demo.py - end-to-end demo of label-free RHO keep/discard (Module 05/08).

Demonstrates Retrospective Harness Optimization (https://arxiv.org/abs/2606.05922):
improve the harness from past tasks with NO labels, keeping a candidate only if
the agent's own pairwise self-preference favors it.

Key lesson (verified live): self-preference can only DISCRIMINATE when the two
prompts actually produce different-quality answers. On easy tasks a capable agent
answers correctly regardless of prompt, so every comparison TIES (net=0 -> discard)
- which is correct. To see an ACCEPT you need a reasoning-sensitive task set where
prompt quality changes the answer. The canonical such regime is chain-of-thought on
multi-step word problems (Wei et al., https://arxiv.org/abs/2201.11903: GSM8K
10.4 -> 40.7), and it shows most clearly on a smaller local model.

Run from the scaffold root:
  AGENT_BACKEND=omlx OMLX_MODEL=<your-coder-model> python -m evolve.rho_demo
  AGENT_BACKEND=vibeproxy python -m evolve.rho_demo   # strong model: expect mostly ties

Observed (oMLX Qwen2.5-Coder-7B): net=3 -> accepted=True, mutation "allow
step-by-step reasoning". Observed (VibeProxy Claude on trivial arithmetic): net=0
-> discarded (correct - nothing to improve).
"""

from __future__ import annotations

import os

from evolve.loop import run_retrospective_step

# Multi-step word problems - answer quality depends on whether the agent reasons.
REASONING_TASKS = [
    "A shop sells pens at 3 for $2. Mia buys 12 pens and pays with a $20 bill. "
    "How much change does she get? Give the final dollar amount.",
    "A tank holds 240 liters. It drains 8 liters per minute for 6 minutes, then is "
    "refilled by 15 liters per minute for 4 minutes. How many liters are in the tank now?",
    "Tom is 4 years older than twice Sam's age. Sam is 9. In 5 years, how old will Tom be?",
]

# A deliberately weak baseline that forbids reasoning - the failure RHO should fix.
NO_COT_BASELINE = (
    "Answer with ONLY the final number, immediately. Do NOT think step by step. "
    "Do NOT show any working."
)
REASONING_WEAKNESS = (
    "- failure: gets multi-step word problems wrong because it answers immediately "
    "without showing intermediate steps (root cause: prompt forbids step-by-step reasoning)"
)


def main() -> None:
    backend = os.getenv("AGENT_BACKEND", "omlx")
    print(f"[rho_demo] backend={backend}; re-solving {len(REASONING_TASKS)} reasoning tasks", flush=True)
    res = run_retrospective_step(
        baseline_prompt=NO_COT_BASELINE,
        task_inputs=REASONING_TASKS,
        weaknesses=REASONING_WEAKNESS,
        backend=backend,
    )
    print(f"[rho_demo] accepted={res.accepted}  net_self_preference={res.candidate.score}")
    print(f"[rho_demo] verdict: {res.verdict_reason}")
    print(f"[rho_demo] mutation: {res.candidate.mutation_note}")


if __name__ == "__main__":
    main()
