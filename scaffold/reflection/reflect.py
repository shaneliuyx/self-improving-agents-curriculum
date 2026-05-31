"""
reflection/reflect.py - Structured reflection on agent trajectories.

Given a completed trajectory and outcome, call the LLM to produce structured
lessons, then write those lessons to the memory store as "semantic" memories.

WARNING - Recursive Drift:
  Reflection that only reads its own outputs will drift away from reality over
  time (the agent convinces itself it is improving when it is not). Every
  lesson must be anchored to an OBSERVED OUTCOME from evals/run.py, not to
  the agent's own narrative. The verification gate in verification/gates.py
  is the external signal that prevents drift.

Lesson schema (JSON):
  {
    "what_worked":   "...",
    "what_failed":   "...",
    "root_cause":    "...",
    "heuristic":     "...",
    "confidence":    0.0-1.0,
    "applies_to":    ["task_type", ...]
  }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from backends.adapter import chat
from backends.router import route
from memory.store import MemoryStore
from agent.loop import AgentResult


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Lessons:
    """Structured lessons extracted from a trajectory."""
    what_worked:  str
    what_failed:  str
    root_cause:   str
    heuristic:    str
    confidence:   float                    # 0.0 - 1.0
    applies_to:   list[str] = field(default_factory=list)
    raw_response: str = ""                 # LLM's raw output for debugging

    def to_dict(self) -> dict[str, Any]:
        return {
            "what_worked":  self.what_worked,
            "what_failed":  self.what_failed,
            "root_cause":   self.root_cause,
            "heuristic":    self.heuristic,
            "confidence":   self.confidence,
            "applies_to":   self.applies_to,
        }


# ---------------------------------------------------------------------------
# Reflection prompt
# ---------------------------------------------------------------------------

_REFLECTION_SYSTEM = """\
You are a meta-cognitive evaluator for an AI agent. Your job is to analyse a
completed task trajectory and extract structured lessons.

IMPORTANT - Anchor every lesson to an OBSERVED OUTCOME.
Do NOT speculate about what might have worked. Only report what the trajectory
actually demonstrates. If the trajectory shows failure, say so clearly.

Respond ONLY with valid JSON matching this schema:
{
  "what_worked":  "<one sentence>",
  "what_failed":  "<one sentence, or 'nothing' if task succeeded>",
  "root_cause":   "<one sentence root cause of any failure>",
  "heuristic":    "<one actionable rule for future tasks>",
  "confidence":   <float 0.0-1.0>,
  "applies_to":   ["<task_type>", ...]
}
"""


def _summarise_trajectory(result: AgentResult) -> str:
    """Convert a trajectory to a compact text summary for the LLM."""
    lines = [
        f"Task: {result.task}",
        f"Success: {result.success}",
        f"Stop reason: {result.stop_reason}",
        f"Rounds used: {result.rounds_used}",
        "",
        "Steps:",
    ]
    for step in result.trajectory:
        if step.role == "tool":
            lines.append(
                f"  [Round {step.round_num}] TOOL {step.tool_name}"
                f"({json.dumps(step.tool_args)}) -> {json.dumps(step.tool_result)}"
            )
        else:
            snippet = step.content[:200].replace("\n", " ")
            lines.append(f"  [Round {step.round_num}] {step.role.upper()}: {snippet}")
    lines.append(f"\nFinal answer: {result.answer[:300]}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def reflect_on_trajectory(
    result: AgentResult,
    store: MemoryStore | None = None,
    save_to_memory: bool = True,
) -> Lessons:
    """
    Reflect on a completed agent trajectory and extract structured lessons.

    Args:
        result:         The AgentResult from agent/loop.py.
        store:          MemoryStore to write lessons to. Created if None.
        save_to_memory: Whether to persist lessons as semantic memories.

    Returns:
        Lessons dataclass with structured reflection.
    """
    # Use a "hard" routing decision - reflection needs the best available model
    route_decision = route("hard")
    trajectory_summary = _summarise_trajectory(result)

    messages = [
        {"role": "system", "content": _REFLECTION_SYSTEM},
        {
            "role": "user",
            "content": (
                "Analyse this agent trajectory and return structured lessons as JSON.\n\n"
                f"{trajectory_summary}"
            ),
        },
    ]

    raw = chat(
        messages,
        backend=route_decision.backend,
        temperature=0.2,
        max_tokens=512,
    )

    lessons = _parse_lessons(raw)

    # Save to semantic memory so future tasks can retrieve relevant lessons
    if save_to_memory:
        mem = store or MemoryStore()
        mem.add(
            memory_type="semantic",
            content=lessons.heuristic,
            metadata={
                "task":        result.task,
                "success":     result.success,
                "what_worked": lessons.what_worked,
                "what_failed": lessons.what_failed,
                "root_cause":  lessons.root_cause,
                "confidence":  lessons.confidence,
                "applies_to":  lessons.applies_to,
            },
        )

    return lessons


def _parse_lessons(raw: str) -> Lessons:
    """
    Parse the LLM's JSON response into a Lessons object.
    Falls back to a safe default if parsing fails.
    """
    # Strip markdown fences if the LLM wrapped the JSON
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        ).strip()

    try:
        data = json.loads(text)
        return Lessons(
            what_worked  = str(data.get("what_worked",  "unknown")),
            what_failed  = str(data.get("what_failed",  "unknown")),
            root_cause   = str(data.get("root_cause",   "unknown")),
            heuristic    = str(data.get("heuristic",    "No heuristic extracted.")),
            confidence   = float(data.get("confidence", 0.0)),
            applies_to   = list(data.get("applies_to",  [])),
            raw_response = raw,
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        # Parsing failed - record it honestly rather than silently dropping it
        return Lessons(
            what_worked  = "Could not parse reflection output.",
            what_failed  = "LLM did not return valid JSON.",
            root_cause   = "Reflection prompt may need adjustment.",
            heuristic    = "Verify reflection output format before trusting lessons.",
            confidence   = 0.0,
            applies_to   = ["all"],
            raw_response = raw,
        )
