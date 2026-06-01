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
import re
from dataclasses import dataclass, field
from typing import Any

from backends.adapter import make_client, _with_retry
from backends.router import route
from agent.tools import TOOL_SCHEMAS, dispatch_tool
from agent.quarantine import quarantine
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
# Text-based tool-call fallback (for local models that do not emit the
# structured OpenAI `tool_calls` field - e.g. small models served by oMLX, which
# return the call as text like <tools>{"name": ..., "arguments": {...}}</tools>).
# ---------------------------------------------------------------------------

def _parse_text_tool_calls(content: str) -> list[tuple[str, dict[str, Any]]]:
    """
    Extract (tool_name, arguments) pairs from an assistant message's TEXT when
    the backend did not return structured tool_calls. Handles the common shapes:
    <tool_call>...</tool_call>, <tools>...</tools>, <function_call>...</function_call>,
    ```json fenced blocks, and a bare {...} object with a "name" field.
    """
    calls: list[tuple[str, dict[str, Any]]] = []
    if not content:
        return calls
    candidates: list[str] = []
    for tag in ("tool_call", "tools", "function_call", "function"):
        candidates += re.findall(rf"<{tag}>\s*(.*?)\s*</{tag}>", content, re.S)
    candidates += re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.S)
    if not candidates:
        m = re.search(r"\{.*\"name\".*\}", content, re.S)
        if m:
            candidates.append(m.group(0))
    for blob in candidates:
        try:
            obj = json.loads(blob)
        except json.JSONDecodeError:
            continue
        for it in (obj if isinstance(obj, list) else [obj]):
            if not isinstance(it, dict) or "name" not in it:
                continue
            name = it.get("name")
            args = it.get("arguments") or it.get("args") or it.get("parameters") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            if isinstance(name, str) and isinstance(args, dict):
                calls.append((name, args))
    return calls


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_agent(
    task: str,
    system_prompt: str | None = None,
    max_rounds: int | None = None,
    backend: str | None = None,
    difficulty: str = "medium",
    system_override: str | None = None,
    memory: Any | None = None,
    log: bool = False,
) -> AgentResult:
    """
    Run the ReAct agent on a single task.

    Args:
        task:            The user's task string.
        system_prompt:   Override the default system prompt (used by evolve/loop.py
                         to test mutated prompts).
        system_override: Alias for system_prompt (used by the eval harness).
        max_rounds:      Override settings.agent_max_rounds.
        backend:         Override the generation backend.
        difficulty:      Task difficulty for model routing - "trivial"|"easy"|
                         "medium"|"hard"|"critical". The eval harness passes
                         task.difficulty so routing is adaptive, not hardcoded.
        memory:          Optional MemoryStore. When provided, relevant past
                         lessons are retrieved and injected BEFORE the loop -
                         this is the read side of the experience layer (Module 04).

    Returns:
        AgentResult with answer, full trajectory, and metadata.
    """
    max_r = max_rounds or settings.agent_max_rounds
    sys_prompt = system_override or system_prompt or _build_system_prompt()

    # Route by the task's difficulty (not a hardcoded constant), and HONOR the
    # routed model - make_client() returns the backend default, so we must pass
    # route_decision.model through to actually change model size.
    route_decision = route(difficulty)
    effective_backend = backend or route_decision.backend
    client, default_model = make_client(effective_backend)
    # Use the routed model unless the caller forced a different backend (in which
    # case the routed model may not exist on it, so fall back to that backend's default).
    model = route_decision.model if backend is None else default_model

    # Optional durable run log (observability + replay substrate). Off by
    # default so the test suite doesn't litter logs/; scripts/go turns it on.
    logger = None
    if log:
        import uuid
        from agent.runlog import RunLogger
        logger = RunLogger(run_id=uuid.uuid4().hex[:8])
        logger.run_start(task, effective_backend, model)

    # Read side of the experience layer: inject relevant past lessons before ACT.
    # Without this, reflection writes lessons the loop never reads (write-only gap).
    if memory is not None:
        mem_ctx = memory.inject_context(task)
        if mem_ctx:
            sys_prompt = f"{sys_prompt}\n\n{mem_ctx}"

    # Build the conversation history
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": sys_prompt},
        {"role": "user",   "content": task},
    ]

    trajectory: list[TrajectoryStep] = []
    answer = ""
    stop_reason = "max_rounds"
    total_tokens = 0   # token telemetry accumulator (TPM/RPM visibility)

    try:
      for round_num in range(1, max_r + 1):
        try:
            # _with_retry handles transient 429/5xx/timeout/connection blips
            # with capped backoff; a single rate-limit must not end the run.
            response = _with_retry(lambda: client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=1024,
            ))
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

        # Token telemetry: accumulate usage when the backend reports it.
        if getattr(response, "usage", None) is not None:
            total_tokens += getattr(response.usage, "total_tokens", 0) or 0

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

                # Feed observation back - QUARANTINED. Tool output is untrusted
                # (a file/API can carry injected instructions); framing it as
                # data keeps it out of the instruction channel. The trajectory
                # step above keeps the RAW result so the run log stays truthful.
                messages.append({
                    "role":         "tool",
                    "tool_call_id": tc.id,
                    "content":      quarantine(result_text, source=tc.function.name),
                })

        # --- Case 1b: text-based tool calls (local models that do not emit
        # the structured tool_calls field - e.g. small models served by oMLX) ---
        elif (text_calls := _parse_text_tool_calls(message.content or "")):
            messages.append({"role": "assistant", "content": message.content or ""})
            for name, args in text_calls:
                tool_result = dispatch_tool(name, args)
                result_text = json.dumps(tool_result)
                trajectory.append(TrajectoryStep(
                    round_num=round_num, role="tool", content=result_text,
                    tool_name=name, tool_args=args, tool_result=tool_result,
                ))
                # No tool_call_id exists for a text-parsed call, so feed the
                # observation back as a user turn (stays OpenAI-compatible).
                # Same quarantine framing - untrusted output stays untrusted on
                # the text path too.
                messages.append({
                    "role": "user",
                    "content": f"Tool {name} returned:\n{quarantine(result_text, source=name)}\nUse it to give the final answer.",
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
    except KeyboardInterrupt:
        # Cooperative cancel: a Ctrl-C mid-run finalizes cleanly with the
        # partial trajectory preserved (and flushed to the run log below)
        # instead of propagating and losing everything done so far.
        stop_reason = "interrupted"
        answer = answer or "[interrupted by user]"

    success = (stop_reason == "answer" and bool(answer))

    # Durable observability: serialize every step + token total to the JSONL run
    # log (the shared substrate for agent/replay.py). Only when log=True.
    if logger is not None:
        for s in trajectory:
            logger.step(s.round_num, s.role, s.content,
                        tool_name=s.tool_name, tool_args=s.tool_args)
        logger.run_end(answer, success, stop_reason, len(trajectory),
                       total_usage={"total_tokens": total_tokens})

    return AgentResult(
        task=task,
        answer=answer,
        trajectory=trajectory,
        success=success,
        rounds_used=len(trajectory),
        stop_reason=stop_reason,
    )
