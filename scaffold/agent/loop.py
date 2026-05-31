"""
agent/loop.py - The ReAct ACT->observe loop.

ReAct (Reason + Act) pattern:
  1. The LLM reasons about the task and optionally calls a tool.
  2. The tool result is fed back as an "observation".
  3. Repeat until the LLM produces a final answer (no tool call) or max_rounds
     is reached.

The full trajectory (every thought, tool call, observation, and final answer)
is returned so it can be passed to memory/store.py and reflection/reflect.py.

References:
  - The minimal agent loop is Module 03 of the curriculum.
  - Trajectory recording feeds Module 04 (Memory Systems).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from backends.adapter import make_client
from backends.router import route
from agent.tools import TOOL_SCHEMAS, dispatch_tool
from config import settings


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TrajectoryStep:
    """One round of the ReAct loop."""
    round_num: int
    role: str            # "assistant" or "tool"
    content: str         # text content or tool result JSON
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    tool_result: dict = field(default_factory=dict)


@dataclass
class AgentResult:
    """Returned by run_agent() after the loop completes."""
    task: str
    answer: str
    trajectory: list[TrajectoryStep]
    success: bool
    rounds_used: int
    stop_reason: str     # "answer", "max_rounds", "error"


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

def _build_system_prompt() -> str:
    """Build the agent system prompt from GOAL.md and AGENTS.md."""
    goal_path  = settings.project_root / "GOAL.md"
    agents_path = settings.project_root / "AGENTS.md"

    goal_text  = goal_path.read_text()  if goal_path.exists()  else "Be helpful."
    agents_text = agents_path.read_text() if agents_path.exists() else ""

    return (
        "You are a self-improving agent. Your goal:\n\n"
        f"{goal_text}\n\n"
        "--- Operating Contract ---\n"
        f"{agents_text}\n\n"
        "Use the available tools when you need to compute or look up information. "
        "When you have a final answer, respond with plain text (no tool call)."
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_agent(
    task: str,
    system_prompt: str | None = None,
    max_rounds: int | None = None,
    backend: str | None = None,
) -> AgentResult:
    """
    Run the ReAct agent on a single task.

    Args:
        task:           The user's task string.
        system_prompt:  Override the default system prompt (used by evolve/loop.py
                        to test mutated prompts).
        max_rounds:     Override settings.agent_max_rounds.
        backend:        Override the generation backend.

    Returns:
        AgentResult with answer, full trajectory, and metadata.
    """
    max_r = max_rounds or settings.agent_max_rounds
    sys_prompt = system_prompt or _build_system_prompt()

    # Route based on task difficulty (medium = general tasks)
    route_decision = route("medium")
    effective_backend = backend or route_decision.backend
    client, model = make_client(effective_backend)

    # Build the conversation history
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": sys_prompt},
        {"role": "user",   "content": task},
    ]

    trajectory: list[TrajectoryStep] = []
    answer = ""
    stop_reason = "max_rounds"

    for round_num in range(1, max_r + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=1024,
            )
        except Exception as exc:
            # Surface errors in the trajectory - never silently swallow them
            error_step = TrajectoryStep(
                round_num=round_num,
                role="error",
                content=str(exc),
            )
            trajectory.append(error_step)
            stop_reason = "error"
            answer = f"[Error in round {round_num}: {exc}]"
            break

        choice = response.choices[0]
        message = choice.message

        # --- Case 1: the LLM wants to call a tool ---
        if message.tool_calls:
            # Append the assistant's tool-call message to history
            messages.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id":   tc.id,
                        "type": tc.type,
                        "function": {
                            "name":      tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ],
            })

            # Execute each tool call and collect results
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                tool_result = dispatch_tool(tc.function.name, args)
                result_text = json.dumps(tool_result)

                # Record step
                step = TrajectoryStep(
                    round_num=round_num,
                    role="tool",
                    content=result_text,
                    tool_name=tc.function.name,
                    tool_args=args,
                    tool_result=tool_result,
                )
                trajectory.append(step)

                # Feed observation back into messages
                messages.append({
                    "role":         "tool",
                    "tool_call_id": tc.id,
                    "content":      result_text,
                })

        # --- Case 2: the LLM produced a final answer (no tool call) ---
        else:
            answer = message.content or ""
            step = TrajectoryStep(
                round_num=round_num,
                role="assistant",
                content=answer,
            )
            trajectory.append(step)
            stop_reason = "answer"
            break

    return AgentResult(
        task=task,
        answer=answer,
        trajectory=trajectory,
        success=(stop_reason == "answer" and bool(answer)),
        rounds_used=len(trajectory),
        stop_reason=stop_reason,
    )
