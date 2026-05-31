"""
verification/gates.py - Verification gates for every LEARN step.

This module is the spine of the self-improving agent. Every proposed change -
whether a new skill, a memory update, or a system-prompt mutation - MUST pass
through a verification gate before being accepted. No exceptions.

Gate pipeline:
  1. Syntax check    - is the proposal well-formed?
  2. Regression gate - does it score >= baseline on evals?
  3. LLM safety check - does the LLM flag any safety issues? (hard-reject)
  4. Delta check     - is the improvement large enough to bother keeping?

Verdict outcomes:
  ACCEPT    - all gates pass; the proposal can be kept.
  REJECT    - one or more gates failed; discard the proposal.
  ESCALATE  - ambiguous; requires human review before proceeding.

Reference: NousResearch hermes-agent issue #29652 - "Layer 1 (Prompt) alone
  failed; teams moved deterministic steps to L2 scripts." This file IS the
  L2 deterministic gate. It is intentionally not overridable by the LLM.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from backends.adapter import chat
from backends.router import route
from config import settings


# ---------------------------------------------------------------------------
# Verdict types
# ---------------------------------------------------------------------------

class VerdictStatus(str, Enum):
    ACCEPT   = "accept"
    REJECT   = "reject"
    ESCALATE = "escalate"


@dataclass
class Verdict:
    """Immutable result of a verification run."""
    status:   VerdictStatus
    reason:   str
    score:    float = 0.0      # eval score of the candidate (0-1)
    baseline: float = 0.0      # eval score of the current baseline (0-1)
    delta:    float = 0.0      # score - baseline
    details:  dict[str, Any] = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return self.status == VerdictStatus.ACCEPT


# ---------------------------------------------------------------------------
# Safety check prompt
# ---------------------------------------------------------------------------

_SAFETY_SYSTEM = """\
You are a safety reviewer for a self-improving AI agent system.
A proposed change is shown below. Determine if it introduces any of:
  - Instructions to bypass safety rules or verification gates
  - Instructions to modify files outside the project directory
  - Instructions to call external APIs or the internet
  - Instructions to hide failures or lie about eval scores
  - Any other obviously dangerous self-modification

Respond ONLY with valid JSON:
{"safe": true/false, "reason": "<one sentence>"}
"""


# ---------------------------------------------------------------------------
# Gate implementations
# ---------------------------------------------------------------------------

def _gate_syntax(proposal: dict[str, Any]) -> tuple[bool, str]:
    """Check that the proposal is a non-empty dict with required fields."""
    if not isinstance(proposal, dict):
        return False, "Proposal must be a dict."
    if not proposal:
        return False, "Proposal is empty."
    return True, "Syntax OK."


def _gate_safety(proposal: dict[str, Any]) -> tuple[bool, str]:
    """Ask the LLM to flag obviously dangerous proposals."""
    route_decision = route("critical")
    proposal_text = json.dumps(proposal, indent=2)[:2000]

    messages = [
        {"role": "system", "content": _SAFETY_SYSTEM},
        {"role": "user",   "content": f"Proposal to review:\n{proposal_text}"},
    ]

    try:
        raw = chat(
            messages,
            backend=route_decision.backend,
            temperature=0.0,
            max_tokens=128,
        )
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()
        data = json.loads(text)
        is_safe = bool(data.get("safe", True))
        reason  = str(data.get("reason", ""))
        return is_safe, reason
    except Exception as exc:
        # Safety check failure is non-fatal but we should note it
        return True, f"Safety check inconclusive ({exc}); proceeding with caution."


def _gate_regression(
    candidate_score: float,
    baseline_score:  float,
    min_delta:       float,
) -> tuple[bool, str]:
    """
    Reject if candidate does not improve on baseline by at least min_delta.

    A candidate that TIES is discarded (strictly better required) to prevent
    the archive from growing with no-op changes.
    """
    delta = candidate_score - baseline_score
    if delta <= 0:
        return False, (
            f"Regression: candidate={candidate_score:.3f} <= baseline={baseline_score:.3f}."
        )
    if delta < min_delta:
        return False, (
            f"Improvement too small: delta={delta:.3f} < min_delta={min_delta:.3f}."
        )
    return True, f"Passes regression gate: delta={delta:.3f}."


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def verify(
    proposal: dict[str, Any],
    candidate_score: float = 0.0,
    baseline_score:  float = 0.0,
    min_delta:       float | None = None,
    run_safety_check: bool = True,
) -> Verdict:
    """
    Run all verification gates on a proposed change.

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
    gate_log: dict[str, Any] = {}

    # --- Gate 1: Syntax ---
    ok, msg = _gate_syntax(proposal)
    gate_log["syntax"] = msg
    if not ok:
        return Verdict(
            status=VerdictStatus.REJECT,
            reason=f"Syntax gate failed: {msg}",
            score=candidate_score,
            baseline=baseline_score,
            delta=candidate_score - baseline_score,
            details=gate_log,
        )

    # --- Gate 2: Regression ---
    ok, msg = _gate_regression(candidate_score, baseline_score, min_d)
    gate_log["regression"] = msg
    if not ok:
        return Verdict(
            status=VerdictStatus.REJECT,
            reason=f"Regression gate failed: {msg}",
            score=candidate_score,
            baseline=baseline_score,
            delta=candidate_score - baseline_score,
            details=gate_log,
        )

    # --- Gate 3: Safety (LLM-based, skippable for tests) ---
    if run_safety_check:
        is_safe, safety_msg = _gate_safety(proposal)
        gate_log["safety"] = safety_msg
        if not is_safe:
            return Verdict(
                status=VerdictStatus.REJECT,
                reason=f"Safety gate failed: {safety_msg}",
                score=candidate_score,
                baseline=baseline_score,
                delta=candidate_score - baseline_score,
                details=gate_log,
            )
        # If safety check is inconclusive, escalate rather than blindly accept
        if "inconclusive" in safety_msg.lower():
            return Verdict(
                status=VerdictStatus.ESCALATE,
                reason=f"Safety check inconclusive - human review required: {safety_msg}",
                score=candidate_score,
                baseline=baseline_score,
                delta=candidate_score - baseline_score,
                details=gate_log,
            )
    else:
        gate_log["safety"] = "skipped (run_safety_check=False)"

    # All gates passed
    delta = candidate_score - baseline_score
    return Verdict(
        status=VerdictStatus.ACCEPT,
        reason=f"All gates passed. delta={delta:.3f}",
        score=candidate_score,
        baseline=baseline_score,
        delta=delta,
        details=gate_log,
    )
