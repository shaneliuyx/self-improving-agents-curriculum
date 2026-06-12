"""
evolve/loop.py - DGM-style system-prompt evolution loop.

Inspired by the Darwin Gödel Machine (https://arxiv.org/abs/2505.22954) but
applied ONLY to the agent's SYSTEM PROMPT (not weights or code), making it
safe and reversible. Weight/code self-modification is reserved for narrow,
benchmarkable, sandboxed sub-problems (curriculum thesis: camp 2 + VERIFY).

Algorithm (keep/discard):
  1. Sample a parent system prompt from the archive (or use the baseline).
  2. Ask the LLM to propose one targeted mutation.
  3. Evaluate the mutated prompt on the eval task set.
  4. If strictly better than the current best: add to archive, update best.
  5. Otherwise: discard.
  6. Append the result to evolve/archive/ for auditability.

Every accepted variant is committed via scripts/commit so the improvement
history is fully revertible.

WARNING: This loop modifies the agent's own instructions. The verification
gate (verification/gates.py) is the ONLY thing that prevents the agent from
mutating itself into uselessness. Do not remove or skip the gate.

Two 2026 refinements ship here as opt-in modes (both additive, both keep the
same accept-after-test discipline):

  * Weakness-targeted proposal (Self-Harness, https://arxiv.org/abs/2606.09498):
    pass `weaknesses=` (mined from reflection lessons or failed trajectories) so
    the mutation targets observed failure patterns instead of mutating blind.
    See `mine_weaknesses()` and the `weaknesses` argument of
    `run_evolution_step()`. This closes the REFLECT -> LEARN link: reflection
    output now steers the next mutation.
  * Label-free self-preference (RHO, https://arxiv.org/abs/2606.05922): when you
    have NO eval labels, `run_retrospective_step()` re-solves past tasks with the
    baseline and the candidate and keeps the candidate only if the agent's own
    pairwise self-preference favors it (the safety/containment gate still applies).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from backends.adapter import chat
from backends.router import route
from config import settings


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PromptVariant:
    """A versioned system-prompt candidate."""
    variant_id: str             # e.g. "v0001"
    prompt:     str             # the full system prompt text
    score:      float = 0.0    # eval success rate (0-1)
    parent_id:  str   = ""     # which variant this was mutated from
    mutation_note: str = ""    # one-line description of the mutation
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvolutionResult:
    """Result of a single evolution step."""
    accepted:       bool
    candidate:      PromptVariant
    baseline_score: float
    verdict_reason: str


# ---------------------------------------------------------------------------
# Archive helpers
# ---------------------------------------------------------------------------

def _archive_path(variant_id: str) -> Path:
    return settings.evolve_archive_dir / f"{variant_id}.json"


def _save_variant(variant: PromptVariant) -> None:
    """Persist a variant to evolve/archive/<id>.json."""
    settings.evolve_archive_dir.mkdir(parents=True, exist_ok=True)
    _archive_path(variant.variant_id).write_text(
        json.dumps(variant.to_dict(), indent=2), encoding="utf-8"
    )


def _load_variant(variant_id: str) -> PromptVariant | None:
    p = _archive_path(variant_id)
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    return PromptVariant(**data)


def load_archive() -> list[PromptVariant]:
    """Return all archived variants sorted by score descending."""
    variants = []
    for path in sorted(settings.evolve_archive_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            variants.append(PromptVariant(**data))
        except Exception:
            continue
    variants.sort(key=lambda v: v.score, reverse=True)
    return variants


def best_variant() -> PromptVariant | None:
    """Return the highest-scoring archived variant, or None if archive is empty."""
    archive = load_archive()
    return archive[0] if archive else None


# ---------------------------------------------------------------------------
# Mutation prompt
# ---------------------------------------------------------------------------

_MUTATION_SYSTEM = """\
You are a meta-optimizer for an AI agent system prompt.

Given the current system prompt and its performance, propose ONE targeted
mutation that might improve the agent's task success rate.

Rules:
- Make only ONE change (add a clarification, reorder instructions, add an
  example, remove confusing text, etc.)
- Never remove safety rules or verification gate instructions.
- Never add instructions to call the internet or modify external files.
- Keep the mutated prompt under 2000 characters.

Respond ONLY with valid JSON:
{
  "mutation_note": "<one sentence describing the change>",
  "mutated_prompt": "<the complete new system prompt>"
}
"""


def _propose_mutation(
    parent: PromptVariant,
    weaknesses: str | None = None,
) -> tuple[str, str] | None:
    """
    Ask the LLM to propose one mutation of a parent prompt.

    Args:
        parent:     The prompt variant to mutate.
        weaknesses: Optional text describing observed failure patterns (from
                    `mine_weaknesses()`). When provided, the model is told to
                    target the mutation at these weaknesses - the "Weakness
                    Mining -> Harness Proposal" link of Self-Harness
                    (https://arxiv.org/abs/2606.09498). When None, the proposal
                    is blind (classic DGM behaviour), preserving backward
                    compatibility.

    Returns:
        (mutation_note, mutated_prompt) or None if parsing failed.
    """
    route_decision = route("hard")
    weakness_block = (
        f"\n\nObserved weaknesses to fix (target your mutation at THESE):\n{weaknesses}\n"
        if weaknesses and weaknesses.strip()
        else ""
    )
    messages = [
        {"role": "system", "content": _MUTATION_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Current system prompt (score={parent.score:.3f}):\n\n"
                f"{parent.prompt}\n"
                f"{weakness_block}\n"
                "Propose one mutation to improve task performance."
            ),
        },
    ]

    raw = chat(
        messages,
        backend=route_decision.backend,
        temperature=0.8,   # higher temperature for creative mutations
        max_tokens=1024,
    )

    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()

    try:
        data = json.loads(text)
        note   = str(data.get("mutation_note",  ""))
        prompt = str(data.get("mutated_prompt", ""))
        if not prompt:
            return None
        return note, prompt
    except (json.JSONDecodeError, KeyError):
        return None


# ---------------------------------------------------------------------------
# Main evolution step
# ---------------------------------------------------------------------------

def run_evolution_step(
    baseline_prompt: str,
    baseline_score:  float,
    eval_fn: Any,   # Callable[[str], float] - takes a system prompt, returns score
    weaknesses: str | None = None,
) -> EvolutionResult:
    """
    Run one DGM-style keep/discard evolution step.

    Args:
        baseline_prompt: The current best system prompt text.
        baseline_score:  The baseline eval success rate (0-1).
        eval_fn:         A callable that takes a system prompt string and returns
                         a float score (0-1). Typically evals/run.py:score_prompt().

    Returns:
        EvolutionResult indicating whether the candidate was accepted.
    """
    # Determine parent: use the best archived variant if available, else baseline
    archive = load_archive()
    if archive:
        import random
        # Sample from top-3 to avoid over-exploiting a single parent
        pool = archive[:3]
        parent = random.choice(pool)
    else:
        # Bootstrap: create a v0000 baseline entry
        parent = PromptVariant(
            variant_id    = "v0000",
            prompt        = baseline_prompt,
            score         = baseline_score,
            mutation_note = "baseline",
        )
        _save_variant(parent)

    # Propose a mutation (optionally weakness-targeted - Self-Harness)
    result = _propose_mutation(parent, weaknesses=weaknesses)
    if result is None:
        return EvolutionResult(
            accepted       = False,
            candidate      = parent,
            baseline_score = baseline_score,
            verdict_reason = "Mutation proposal failed or returned empty prompt.",
        )

    mutation_note, mutated_prompt = result

    # Evaluate the candidate
    try:
        candidate_score = eval_fn(mutated_prompt)
    except Exception as exc:
        return EvolutionResult(
            accepted       = False,
            candidate      = parent,
            baseline_score = baseline_score,
            verdict_reason = f"Eval function raised an error: {exc}",
        )

    # Run through the verification gate
    from verification.gates import verify
    verdict = verify(
        proposal         = {"type": "prompt", "content": mutated_prompt, "note": mutation_note},
        candidate_score  = candidate_score,
        baseline_score   = baseline_score,
        run_safety_check = True,
    )

    # Build the variant record
    next_id = f"v{len(archive) + 1:04d}"
    candidate = PromptVariant(
        variant_id    = next_id,
        prompt        = mutated_prompt,
        score         = candidate_score,
        parent_id     = parent.variant_id,
        mutation_note = mutation_note,
    )

    if verdict.accepted:
        _save_variant(candidate)

    return EvolutionResult(
        accepted       = verdict.accepted,
        candidate      = candidate,
        baseline_score = baseline_score,
        verdict_reason = verdict.reason,
    )


# ---------------------------------------------------------------------------
# Weakness mining (Self-Harness, https://arxiv.org/abs/2606.09498)
# ---------------------------------------------------------------------------

def mine_weaknesses(lessons: Any) -> str:
    """
    Turn reflection output into a short, targeted weakness signal for
    `_propose_mutation` / `run_evolution_step(weaknesses=...)`.

    This is the "Weakness Mining" stage of Self-Harness: instead of mutating the
    prompt blind, distil the failure patterns the agent actually hit so the next
    proposal edits the prompt where it breaks. It is the same move agent-prep's
    `learning_extractor.extract()` makes over an observation log - here we read
    the structured lessons that `reflection/reflect.py` already produces.

    Args:
        lessons: a single object exposing `what_failed` / `root_cause`
                 (e.g. reflection.reflect.Lessons), a dict with those keys, or a
                 list of either. Lessons whose failure is empty / "nothing" are
                 skipped (a clean run has no weakness to target).

    Returns:
        A newline-joined "- failure: ... (root cause: ...)" block, or "" if
        there is nothing actionable to mine.
    """
    items = lessons if isinstance(lessons, (list, tuple)) else [lessons]
    lines: list[str] = []
    for item in items:
        if isinstance(item, dict):
            failed = item.get("what_failed")
            cause  = item.get("root_cause")
        else:
            failed = getattr(item, "what_failed", None)
            cause  = getattr(item, "root_cause", None)
        if failed and str(failed).strip().lower() not in ("", "nothing", "none"):
            lines.append(f"- failure: {str(failed).strip()} (root cause: {str(cause or 'unknown').strip()})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Label-free self-preference (RHO, https://arxiv.org/abs/2606.05922)
# ---------------------------------------------------------------------------

_PREFERENCE_SYSTEM = """\
You are comparing two AI agents that attempted the SAME task. You do NOT have a
ground-truth answer. Judge ONLY which response is more correct, complete, and
useful. Be decisive.

Respond ONLY with valid JSON: {"winner": "A" | "B" | "tie", "reason": "<one sentence>"}
"""


def self_preference(
    prompt_a: str,
    prompt_b: str,
    task_inputs: list[str],
    backend: str | None = None,
) -> int:
    """
    Label-free pairwise comparison of two system prompts (RHO,
    https://arxiv.org/abs/2606.05922).

    Re-solves each task in `task_inputs` with both prompts and asks the model to
    pick the better answer WITHOUT any ground-truth label - the same shape as
    agent-prep's `shared/llm.py:judge`, generalised to a pairwise preference.
    Returns the net preference for A over B: positive if A wins more, negative if
    B wins more, 0 on a tie. This is the core of Retrospective Harness
    Optimization: improve from the agent's own past trajectories using
    self-preference instead of labels.
    """
    from agent.loop import run_agent  # lazy import to avoid a module cycle

    net = 0
    for task in task_inputs:
        ans_a = run_agent(task, system_prompt=prompt_a, backend=backend).answer
        ans_b = run_agent(task, system_prompt=prompt_b, backend=backend).answer
        route_decision = route("hard")
        raw = chat(
            [
                {"role": "system", "content": _PREFERENCE_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"Task:\n{task}\n\nResponse A:\n{ans_a}\n\n"
                        f"Response B:\n{ans_b}\n\nWhich response is better?"
                    ),
                },
            ],
            backend=route_decision.backend,
            temperature=0.0,
            max_tokens=200,
        )
        text = raw.strip()
        if text.startswith("```"):
            text = "\n".join(l for l in text.split("\n") if not l.strip().startswith("```")).strip()
        try:
            winner = str(json.loads(text).get("winner", "tie")).upper()
        except (json.JSONDecodeError, KeyError):
            winner = "TIE"
        if winner == "A":
            net += 1
        elif winner == "B":
            net -= 1
    return net


def run_retrospective_step(
    baseline_prompt: str,
    task_inputs: list[str],
    weaknesses: str | None = None,
    backend: str | None = None,
) -> EvolutionResult:
    """
    One label-free evolution step (RHO, https://arxiv.org/abs/2606.05922).

    Unlike `run_evolution_step` (which needs an `eval_fn` returning a labeled
    score), this keeps or discards a candidate purely on the agent's own
    pairwise self-preference over re-solved past tasks - no ground truth, no
    validation set. The safety / containment gate still applies; only the
    regression-by-score check is replaced by self-preference. Optionally pass
    `weaknesses` to combine RHO with Self-Harness weakness targeting.
    """
    parent = PromptVariant(
        variant_id    = "retro-parent",
        prompt        = baseline_prompt,
        score         = 0.0,
        mutation_note = "baseline (retrospective)",
    )
    result = _propose_mutation(parent, weaknesses=weaknesses)
    if result is None:
        return EvolutionResult(
            accepted       = False,
            candidate      = parent,
            baseline_score = 0.0,
            verdict_reason = "Mutation proposal failed or returned empty prompt.",
        )
    mutation_note, mutated_prompt = result

    # Keep decision = the agent's own pairwise self-preference (no labels).
    pref = self_preference(mutated_prompt, baseline_prompt, task_inputs, backend=backend)

    # Safety / containment gate still applies. We encode the self-preference as
    # the (label-free) "score" so the regression gate agrees with it, then AND
    # with pref > 0 so a tie is discarded regardless of the gate's comparison.
    from verification.gates import verify
    verdict = verify(
        proposal         = {"type": "prompt", "content": mutated_prompt, "note": mutation_note},
        candidate_score  = float(max(pref, 0)),
        baseline_score   = 0.0,
        run_safety_check = True,
    )
    accepted = verdict.accepted and pref > 0

    candidate = PromptVariant(
        variant_id    = f"retro-{int(time.time())}",
        prompt        = mutated_prompt,
        score         = float(pref),   # store net self-preference as the label-free score
        parent_id     = parent.variant_id,
        mutation_note = f"{mutation_note} [self-preference net={pref}]",
    )
    if accepted:
        _save_variant(candidate)

    return EvolutionResult(
        accepted       = accepted,
        candidate      = candidate,
        baseline_score = 0.0,
        verdict_reason = (
            f"self-preference net={pref} ({'kept' if accepted else 'discarded'}); "
            f"safety gate: {verdict.reason}"
        ),
    )
