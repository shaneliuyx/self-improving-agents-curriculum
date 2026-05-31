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


def _propose_mutation(parent: PromptVariant) -> tuple[str, str] | None:
    """
    Ask the LLM to propose one mutation of a parent prompt.

    Returns:
        (mutation_note, mutated_prompt) or None if parsing failed.
    """
    route_decision = route("hard")
    messages = [
        {"role": "system", "content": _MUTATION_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Current system prompt (score={parent.score:.3f}):\n\n"
                f"{parent.prompt}\n\n"
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

    # Propose a mutation
    result = _propose_mutation(parent)
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
