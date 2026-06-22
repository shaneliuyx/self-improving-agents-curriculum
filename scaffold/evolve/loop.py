"""
evolve/loop.py - DGM-style system-prompt evolution loop.

Inspired by the Darwin Gödel Machine (https://arxiv.org/abs/2505.22954) but
applied ONLY to the agent's SYSTEM PROMPT (not weights or code), making it
safe and reversible.

THIS IS A FACADE OVER agentkit. The keep/discard CONTROL is NOT hand-rolled
here any more:

  * ``run_evolution_step`` delegates one epoch to ``agentkit.evolve.evolve_prompt``
    (``optimize_text`` over a system prompt), admitting the candidate solely
    through agentkit's LEARN ``Gate``. The lab's archive directory + the
    weakness-targeted proposer stay on top (agentkit keeps its archive in memory;
    the lab persists each accepted variant as a git-revertible JSON file).
  * ``run_retrospective_step`` (RHO, https://arxiv.org/abs/2606.05922) delegates
    to ``agentkit.evolve.evolve_prompt_rho`` - the label-free self-preference loop
    agentkit ported from this very module.
  * ``mine_weaknesses`` (Self-Harness, https://arxiv.org/abs/2606.09498) is the
    one lab-specific bit kept on top: it distils the lab's reflection ``Lessons``
    into the ``weaknesses=`` string agentkit's ``make_llm_proposer`` targets.

The lab's public surface (``PromptVariant`` / ``EvolutionResult`` /
``run_evolution_step`` / ``run_retrospective_step`` / ``mine_weaknesses`` /
``self_preference`` / ``load_archive`` / ``best_variant``) is preserved so the
behavior eval and the RHO demo keep working; only the BODIES delegate to agentkit.

WARNING: This loop modifies the agent's own instructions. agentkit's verification
gate is the ONLY thing that prevents the agent from mutating itself into
uselessness. Do not remove or skip the gate.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from config import settings

from agentkit.evolve import (
    evolve_prompt,
    make_llm_proposer,
    optimize_text,
    self_preference as _ak_self_preference,
)
from agentkit.gates import Gate
from agentkit.sandbox import SubprocessSandbox


# ---------------------------------------------------------------------------
# Data structures (the lab's public shape)
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
# Archive helpers (lab-side persistence: agentkit keeps the archive in memory,
# the lab writes each accepted variant as a git-revertible file for auditability)
# ---------------------------------------------------------------------------

def _archive_path(variant_id: str) -> Path:
    return settings.evolve_archive_dir / f"{variant_id}.json"


def _save_variant(variant: PromptVariant) -> None:
    """Persist a variant to evolve/archive/<id>.json."""
    settings.evolve_archive_dir.mkdir(parents=True, exist_ok=True)
    _archive_path(variant.variant_id).write_text(
        json.dumps(variant.to_dict(), indent=2), encoding="utf-8"
    )


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
# Backend wiring for agentkit's injected proposer / RHO client
# ---------------------------------------------------------------------------

def _client(backend: str | None = None) -> Any:
    """Build the agentkit ``LLMClient`` the proposer / RHO judge run on."""
    from backends.adapter import BACKENDS, OMLXClient
    from backends.router import route

    eff = backend or route("hard").backend
    cfg = BACKENDS[eff]
    return OMLXClient(model=cfg["model"], base_url=cfg["base_url"])


def _gate(evaluator: Any, client: Any | None = None) -> Gate:
    """agentkit's LEARN gate, jailed to the archive dir for sandbox execution.

    agentkit's ``optimize_text`` admits each candidate via ``gate.run_gate`` and
    the gate's OWN evaluator is what its regression/delta stages score against -
    so the gate evaluator must be the same scoring the loop ranks by. The gate
    evaluator receives the proposal DICT, so it reads ``proposal["content"]``.
    """
    settings.evolve_archive_dir.mkdir(parents=True, exist_ok=True)
    return Gate(
        sandbox=SubprocessSandbox(),
        evaluator=evaluator,
        client=client,
        cwd=settings.evolve_archive_dir,
    )


# ---------------------------------------------------------------------------
# Weakness mining (Self-Harness) - the one lab-specific bit kept on top
# ---------------------------------------------------------------------------

def mine_weaknesses(lessons: Any) -> str:
    """
    Turn reflection output into a short, targeted weakness signal for agentkit's
    weakness-aware proposer (``make_llm_proposer(weaknesses=...)``).

    This is the "Weakness Mining" stage of Self-Harness
    (https://arxiv.org/abs/2606.09498): instead of mutating the prompt blind,
    distil the failure patterns the agent actually hit so the next proposal edits
    the prompt where it breaks. agentkit does not know the lab's ``Lessons``
    shape, so this stays lab-side; its output feeds straight into agentkit.

    Args:
        lessons: a single object exposing ``what_failed`` / ``root_cause``
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
# Main evolution step (delegates to agentkit.evolve.evolve_prompt)
# ---------------------------------------------------------------------------

def run_evolution_step(
    baseline_prompt: str,
    baseline_score:  float,
    eval_fn: Any,   # Callable[[str], float] - takes a system prompt, returns score
    weaknesses: str | None = None,
) -> EvolutionResult:
    """
    Run one DGM-style keep/discard evolution step, via agentkit's optimizer.

    The proposer is agentkit's weakness-aware ``make_llm_proposer`` (the
    Self-Harness "harness proposal" stage); the keep/discard CONTROL and the
    admission gate are agentkit's. ``eval_fn`` is agentkit's evaluator, so the
    regression/delta decision is computed by agentkit against ``baseline_score``.
    An accepted variant is then persisted to the lab's git-revertible archive.

    Args:
        baseline_prompt: The current best system prompt text.
        baseline_score:  The baseline eval success rate (0-1).
        eval_fn:         A callable that takes a system prompt string and returns
                         a float score (0-1). Typically evals/run.py:score_prompt().
        weaknesses:      Optional weakness signal (from ``mine_weaknesses``) to
                         target the mutation (Self-Harness). None = blind (DGM).

    Returns:
        EvolutionResult indicating whether the candidate was accepted.
    """
    archive = load_archive()
    parent_id = archive[0].variant_id if archive else "v0000"

    client = _client()
    proposer = make_llm_proposer(client, weaknesses=weaknesses)

    def evaluate(text: str) -> float:
        try:
            return float(eval_fn(text))
        except Exception:
            return 0.0

    # The gate scores the proposal DICT; the loop scores the candidate TEXT -
    # both must run the SAME eval_fn so the gate's regression stage and the
    # loop's strict-improvement check agree (agentkit's optimize_text contract).
    result = evolve_prompt(
        baseline_prompt,
        propose=proposer,
        evaluate=evaluate,
        gate=_gate(lambda proposal: evaluate(str(proposal.get("content", "")))),
        baseline_score=baseline_score,
        epochs=1,
        cwd=settings.evolve_archive_dir,
    )

    accepted = result.accepted > 0
    note = result.archive[-1].note if result.archive else "no proposal"
    candidate = PromptVariant(
        variant_id    = f"v{len(archive) + 1:04d}",
        prompt        = result.best,
        score         = result.best_score,
        parent_id     = parent_id,
        mutation_note = note,
    )
    if accepted:
        _save_variant(candidate)

    return EvolutionResult(
        accepted       = accepted,
        candidate      = candidate,
        baseline_score = baseline_score,
        verdict_reason = (
            f"agentkit gate kept {result.accepted}/{result.epochs} epoch(s); "
            f"delta={result.delta:+.3f}"
        ),
    )


# ---------------------------------------------------------------------------
# Label-free self-preference (RHO) - re-solve-then-judge over the lab agent.
# This shape (re-solve each task with the lab agent, then judge the ANSWERS) is
# lab-specific; agentkit's self_preference judges prompt TEXTS directly. Kept as
# a lab convenience; run_retrospective_step below uses agentkit's RHO loop.
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
    Label-free pairwise comparison of two system prompts by RE-SOLVING each task
    with the lab agent and judging the answers (RHO, the answer-space variant).

    Returns the net preference for A over B: positive if A wins more, negative if
    B wins more, 0 on a tie. ``run_retrospective_step`` uses agentkit's
    prompt-space RHO loop directly; this helper is the lab's answer-space variant.
    """
    from agent.loop import run_agent  # lazy import to avoid a module cycle
    from backends.adapter import chat
    from backends.router import route

    net = 0
    for task in task_inputs:
        ans_a = run_agent(task, system_prompt=prompt_a, backend=backend).answer
        ans_b = run_agent(task, system_prompt=prompt_b, backend=backend).answer
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
            backend=route("hard").backend,
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
    One label-free evolution step (RHO, https://arxiv.org/abs/2606.05922),
    delegated to ``agentkit.evolve.evolve_prompt_rho``.

    Unlike ``run_evolution_step`` (which needs a labeled ``eval_fn``), agentkit's
    RHO loop keeps or discards a candidate purely on the agent's own pairwise
    self-preference over ``judge_inputs`` - no ground truth, no validation set.
    The safety / containment gate still applies. Optionally pass ``weaknesses`` to
    combine RHO with Self-Harness weakness targeting.
    """
    client = _client(backend)
    proposer = make_llm_proposer(client, weaknesses=weaknesses)

    # RHO scores a candidate by the agent's own pairwise self-preference over the
    # baseline (net positive = better), with NO labels - agentkit's
    # ``self_preference``. The gate evaluator and the loop evaluator both run it
    # so the gate's regression stage agrees with the keep decision.
    def rho_score(candidate: str) -> float:
        return float(max(_ak_self_preference(
            client, candidate, baseline_prompt, judge_inputs=task_inputs
        ), 0))

    result = optimize_text(
        baseline_prompt,
        propose=proposer,
        evaluate=rho_score,
        gate=_gate(lambda proposal: rho_score(str(proposal.get("content", ""))), client),
        baseline_score=0.0,
        epochs=1,
        proposal_type="prompt",
        cwd=settings.evolve_archive_dir,
    )

    accepted = result.accepted > 0
    candidate = PromptVariant(
        variant_id    = f"retro-{int(time.time())}",
        prompt        = result.best,
        score         = result.best_score,
        parent_id     = "retro-parent",
        mutation_note = (result.archive[-1].note if result.archive else "rho") +
                        f" [self-preference, delta={result.delta:+.3f}]",
    )
    if accepted:
        _save_variant(candidate)

    return EvolutionResult(
        accepted       = accepted,
        candidate      = candidate,
        baseline_score = 0.0,
        verdict_reason = (
            f"RHO self-preference kept {result.accepted}/{result.epochs} "
            f"({'kept' if accepted else 'discarded'}); delta={result.delta:+.3f}"
        ),
    )
