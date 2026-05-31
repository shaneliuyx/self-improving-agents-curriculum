"""
evals/run.py - Run the agent over the eval task set and report results.

The eval harness is the external signal that anchors the self-improvement
loop. Without it, reflection degenerates into the agent patting itself on
the back for changes that made no measurable difference.

Usage:
  # Run baseline
  report = run_evals()
  print(f"Score: {report.score:.2%}")

  # Compare a candidate system prompt against the baseline
  candidate_score = score_prompt(new_prompt)
  delta = candidate_score - report.score

  # Run from CLI
  python -m evals.run
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from agent.loop import run_agent, AgentResult
from evals.tasks import TASKS, Task


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TaskResult:
    """Result of running the agent on a single eval task."""
    task_id:   str
    passed:    bool
    answer:    str
    duration:  float     # seconds
    rounds:    int
    stop_reason: str


@dataclass
class EvalReport:
    """Aggregated results over the full task set."""
    score:        float             # success rate 0-1
    total:        int
    passed:       int
    failed:       int
    results:      list[TaskResult] = field(default_factory=list)
    duration:     float = 0.0      # total wall-clock seconds
    system_prompt: str = ""        # the prompt used for this run

    def summary(self) -> str:
        lines = [
            f"Eval score: {self.score:.1%}  ({self.passed}/{self.total} passed)"
            f"  [{self.duration:.1f}s]",
        ]
        for r in self.results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(
                f"  [{status}] {r.task_id:12s}  rounds={r.rounds}"
                f"  stop={r.stop_reason}"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

def run_evals(
    tasks: list[Task] | None = None,
    system_prompt: str | None = None,
    backend: str | None = None,
    verbose: bool = False,
) -> EvalReport:
    """
    Run the agent over the eval task set and return a scored report.

    Args:
        tasks:         Override the default TASKS list (for targeted testing).
        system_prompt: Override the agent's system prompt (for variant comparison).
        backend:       Override the generation backend.
        verbose:       Print progress to stdout.

    Returns:
        EvalReport with per-task results and an overall score.
    """
    task_list = tasks or TASKS
    results: list[TaskResult] = []
    wall_start = time.time()

    for task in task_list:
        if verbose:
            print(f"  Running task {task.id} ...", end=" ", flush=True)

        t0 = time.time()
        try:
            agent_result: AgentResult = run_agent(
                task=task.input,
                system_prompt=system_prompt,
                backend=backend,
            )
            passed = task.checker(agent_result.answer)
            answer = agent_result.answer
            rounds = agent_result.rounds_used
            stop   = agent_result.stop_reason
        except Exception as exc:
            passed = False
            answer = f"[Exception: {exc}]"
            rounds = 0
            stop   = "error"

        duration = time.time() - t0

        task_result = TaskResult(
            task_id    = task.id,
            passed     = passed,
            answer     = answer,
            duration   = duration,
            rounds     = rounds,
            stop_reason = stop,
        )
        results.append(task_result)

        if verbose:
            print("PASS" if passed else "FAIL")

    total  = len(results)
    passed_count = sum(1 for r in results if r.passed)
    score  = passed_count / total if total > 0 else 0.0

    return EvalReport(
        score         = score,
        total         = total,
        passed        = passed_count,
        failed        = total - passed_count,
        results       = results,
        duration      = time.time() - wall_start,
        system_prompt = system_prompt or "",
    )


def score_prompt(
    system_prompt: str,
    backend: str | None = None,
) -> float:
    """
    Convenience function: evaluate a system prompt and return just the score.

    Used by evolve/loop.py as the eval_fn argument.

    Args:
        system_prompt: The system prompt text to evaluate.
        backend:       Optional backend override.

    Returns:
        Success rate as a float 0-1.
    """
    report = run_evals(system_prompt=system_prompt, backend=backend)
    return report.score


def compare(
    baseline_prompt: str,
    candidate_prompt: str,
    backend: str | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """
    Compare a candidate system prompt against a baseline.

    Args:
        baseline_prompt:  The current system prompt.
        candidate_prompt: The proposed mutated prompt.
        backend:          Optional backend override.
        verbose:          Print results to stdout.

    Returns:
        Dict with baseline_score, candidate_score, delta, regression.
    """
    if verbose:
        print("Running baseline eval...")
    baseline  = run_evals(system_prompt=baseline_prompt,  backend=backend, verbose=verbose)
    if verbose:
        print("Running candidate eval...")
    candidate = run_evals(system_prompt=candidate_prompt, backend=backend, verbose=verbose)

    delta = candidate.score - baseline.score
    result = {
        "baseline_score":  baseline.score,
        "candidate_score": candidate.score,
        "delta":           delta,
        "regression":      delta < 0,
    }

    if verbose:
        print(f"\nBaseline:  {baseline.score:.1%}")
        print(f"Candidate: {candidate.score:.1%}")
        print(f"Delta:     {delta:+.1%}  {'(REGRESSION)' if delta < 0 else '(improvement)' if delta > 0 else '(no change)'}")

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    verbose = "--quiet" not in sys.argv
    print("Running eval suite...")
    report = run_evals(verbose=verbose)
    print()
    print(report.summary())
    sys.exit(0 if report.score >= 0.5 else 1)
