"""
verification/gates.py - Verification gates for every LEARN step.

This module is the spine of the self-improving agent. Every proposed change -
whether a new skill, a memory update, or a system-prompt mutation - MUST pass
through a verification gate before being accepted. No exceptions.

THIS IS A FACADE OVER agentkit. The keep/discard pipeline is NOT hand-rolled
here any more: ``verify()`` builds an ``agentkit.gates.Gate`` and runs the same
deterministic, LLM-non-overridable admission pipeline agentkit ships (syntax ->
containment -> sandbox-execute -> regression -> safety -> delta). The lab's
public surface (``VerdictStatus`` / ``Verdict`` / ``verify`` / ``requires_sandbox``)
is preserved exactly so the behavior eval and the evolve loop keep working; only
the BODY now delegates to agentkit.

Verdict outcomes (mapped 1:1 from agentkit's ``Outcome``):
  ACCEPT    - all gates pass; the proposal can be kept.
  REJECT    - one or more gates failed; discard the proposal.
  ESCALATE  - ambiguous / side-effecting; requires human review before proceeding.

Reference: NousResearch hermes-agent issue #29652 - "Layer 1 (Prompt) alone
  failed; teams moved deterministic steps to L2 scripts." agentkit's ``Gate`` IS
  the L2 deterministic gate. It is intentionally not overridable by the LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from config import settings

# Delegate the whole admission pipeline to agentkit's LEARN gate.
from agentkit.gates import Gate, Outcome, Verdict as _AgentkitVerdict
from agentkit.gates.core import _SANDBOX_TOKENS as _AGENTKIT_SANDBOX_TOKENS
from agentkit.sandbox import SubprocessSandbox


# ---------------------------------------------------------------------------
# Verdict types (the lab's public surface; mapped from agentkit.gates.Outcome)
# ---------------------------------------------------------------------------

class VerdictStatus(str, Enum):
    ACCEPT   = "accept"
    REJECT   = "reject"
    ESCALATE = "escalate"


# agentkit.gates.Outcome shares the same three string values, so the mapping is
# value-preserving in both directions.
_OUTCOME_TO_STATUS: dict[Outcome, VerdictStatus] = {
    Outcome.ACCEPT:   VerdictStatus.ACCEPT,
    Outcome.REJECT:   VerdictStatus.REJECT,
    Outcome.ESCALATE: VerdictStatus.ESCALATE,
}


@dataclass
class Verdict:
    """Immutable result of a verification run (the lab's verdict shape)."""
    status:   VerdictStatus
    reason:   str
    score:    float = 0.0      # eval score of the candidate (0-1)
    baseline: float = 0.0      # eval score of the current baseline (0-1)
    delta:    float = 0.0      # score - baseline
    details:  dict[str, Any] = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return self.status == VerdictStatus.ACCEPT

    @classmethod
    def _from_agentkit(cls, v: _AgentkitVerdict) -> "Verdict":
        """Map an ``agentkit.gates.Verdict`` onto the lab's ``Verdict``."""
        return cls(
            status   = _OUTCOME_TO_STATUS[v.status],
            reason   = v.reason,
            score    = v.score,
            baseline = v.baseline,
            delta    = v.delta,
            details  = dict(v.details),
        )


# ---------------------------------------------------------------------------
# Containment: the deterministic, always-on safety floor
# ---------------------------------------------------------------------------
# agentkit's gate ESCALATEs any proposal whose source contains a side-effecting
# capability token (_AGENTKIT_SANDBOX_TOKENS) - the same L2 floor this module
# used to hand-roll. ``requires_sandbox`` is the lab-facing helper over that scan
# (agentkit does not export a standalone predicate, so this thin wrapper is the
# one lab-specific bit kept on top). It adds ``open(`` to agentkit's set so a
# bare file-open in a proposed skill is also flagged for review, matching the
# contract documented in Module 11 §4.4.
SANDBOX_REQUIRED_FOR = ["filesystem", "subprocess", "network", "eval", "exec"]

_SANDBOX_TOKENS: tuple[str, ...] = (*_AGENTKIT_SANDBOX_TOKENS, "open(")


def requires_sandbox(skill_code: str) -> bool:
    """True if proposed skill code touches a capability that must be sandboxed
    (filesystem / subprocess / network / eval / exec).

    Deterministic and free - the lab-facing predicate over agentkit's containment
    token set (plus ``open(``). This is the always-on floor beneath the optional
    LLM safety gate; agentkit's ``Gate`` enforces the same tokens internally.
    """
    return any(token in skill_code for token in _SANDBOX_TOKENS)


# ---------------------------------------------------------------------------
# Main entry point (delegates to agentkit's Gate)
# ---------------------------------------------------------------------------

def _safety_client() -> Any | None:
    """Build the optional LLM ``client`` for agentkit's safety stage.

    agentkit's gate runs its (LLM) safety stage only when a ``client`` is passed,
    and that client can only ADD a rejection - never grant acceptance. The lab
    wires its own ``OMLXClient`` here; if the backend can't be constructed the
    safety stage is simply skipped (the deterministic floor still applies).
    """
    try:
        from backends.adapter import OMLXClient
        return OMLXClient()
    except Exception:
        return None


def verify(
    proposal: dict[str, Any],
    candidate_score: float = 0.0,
    baseline_score:  float = 0.0,
    min_delta:       float | None = None,
    run_safety_check: bool = True,
) -> Verdict:
    """
    Run all verification gates on a proposed change, via agentkit's ``Gate``.

    The lab already KNOWS the candidate's eval score, so the gate's evaluator is
    injected as a constant ``lambda _: candidate_score`` - agentkit then runs the
    same regression/delta logic against ``baseline_score``. ``proposal`` carries
    no executable ``code`` for prompt/skill text, so the gate's sandbox-execute
    stage is a no-op for these proposals (it only runs when ``code`` is present).

    Args:
        proposal:         Dict describing the proposed change. At minimum:
                          {"type": "skill"|"prompt", "content": "..."}
        candidate_score:  Eval success rate (0-1) of the candidate version.
        baseline_score:   Eval success rate (0-1) of the current baseline.
        min_delta:        Minimum improvement required. Defaults to
                          settings.evolve_min_delta.
        run_safety_check: Whether to run the LLM safety gate (can be disabled
                          for unit tests, but never disable in production).

    Returns:
        Verdict with status ACCEPT, REJECT, or ESCALATE.
    """
    min_d = min_delta if min_delta is not None else settings.evolve_min_delta
    client = _safety_client() if run_safety_check else None

    gate = Gate(
        sandbox   = SubprocessSandbox(),
        evaluator = lambda _proposal: candidate_score,
        client    = client,
    )
    agentkit_verdict = gate.run_gate(
        proposal,
        baseline_score = baseline_score,
        min_delta      = min_d,
    )
    return Verdict._from_agentkit(agentkit_verdict)
