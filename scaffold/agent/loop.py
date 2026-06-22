"""
agent/loop.py - The ReAct ACT->observe loop.

ReAct (Reason + Act) pattern:
  1. The LLM reasons about the task and optionally calls a tool.
  2. The tool result is fed back as an "observation".
  3. Repeat until the LLM produces a final answer (no tool call) or max_rounds
     is reached.

THIS IS A FACADE OVER agentkit. The loop itself is NOT hand-rolled here any
more: ``run_agent`` delegates to ``agentkit.agent.run_agent`` (the same ReAct
ACT->observe loop, with the structured + text tool-call paths and the quarantine
of untrusted tool output). What stays lab-side is the operator wiring agentkit
deliberately leaves injected:

  * the BACKEND + difficulty ROUTING (``backends.router.route`` + an
    ``OMLXClient`` over the routed model) - agentkit takes a ready ``LLMClient``,
  * the default SYSTEM PROMPT assembled from GOAL.md + AGENTS.md,
  * the lab TOOL REGISTRY (``agent/tools.py``: ``TOOL_SCHEMAS`` + ``dispatch_tool``),
  * the optional durable RUN LOG (``agent/runlog.py``) for replay/observability.

agentkit's ``AgentResult`` / ``TrajectoryStep`` share this module's field names,
so the result is mapped 1:1 back onto the lab's dataclasses - reflection,
evals/run.py and scripts/show_trajectory.py keep importing them unchanged.

References:
  - The minimal agent loop is Module 03 of the curriculum.
  - Trajectory recording feeds Module 04 (Memory Systems).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent.tools import TOOL_SCHEMAS, dispatch_tool
from backends.router import route
from config import settings

from agentkit.agent import run_agent as _agentkit_run_agent


# ---------------------------------------------------------------------------
# Data structures (the lab's public shape; field-identical to agentkit's, so
# reflection / evals / show_trajectory keep importing them)
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
# Lab tool wiring (kept on top of agentkit - the agentkit gap is that it does
# not ship the lab's calculator/read_file/edit_file tools; agentkit only defines
# the ToolRegistry protocol). This adapter exposes the lab's real JSON schemas
# and dispatcher to agentkit's loop.
# ---------------------------------------------------------------------------

class _LabToolRegistry:
    """Adapt ``agent/tools.py`` to agentkit's ``ToolRegistry`` protocol.

    ``schemas`` are the lab's full OpenAI function schemas (richer than the empty
    params a plain dict-registry would synthesize); ``dispatch`` is the lab's
    ``dispatch_tool``. This is the one lab-specific seam agentkit's loop runs on.
    """

    def __init__(self) -> None:
        self.schemas = TOOL_SCHEMAS

    def dispatch(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        return dispatch_tool(name, args)


def _tool_use_instructions() -> str:
    """Describe the lab's tools IN the system prompt so a local model can call them.

    agentkit's loop reads tool calls from the response (structured ``tool_calls``
    OR a text ``<tool_call>{...}</tool_call>`` block parsed by
    ``_parse_text_tool_calls``). The lab's agentkit ``OMLXClient`` does not forward
    the ``tools`` schema to the API (small local models use the text path), so the
    model only knows a tool exists if it is described here. This in-prompt schema
    is the lab tool-wiring agentkit deliberately leaves to the operator.
    """
    lines = []
    for schema in TOOL_SCHEMAS:
        fn = schema.get("function", schema)
        name = fn.get("name", "")
        desc = fn.get("description", "")
        params = fn.get("parameters", {}).get("properties", {})
        arg_names = ", ".join(params.keys())
        lines.append(f"- {name}({arg_names}): {desc}")
    tool_list = "\n".join(lines)
    return (
        "\n\n--- Tools ---\n"
        "You can call a tool by emitting EXACTLY one line of the form:\n"
        '<tool_call>{"name": "<tool>", "arguments": {<args>}}</tool_call>\n'
        "Available tools:\n"
        f"{tool_list}\n"
        "After a tool returns, use its result to produce the final answer."
    )


# ---------------------------------------------------------------------------
# System prompt (lab-specific: assembled from GOAL.md + AGENTS.md)
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
# Main loop (delegates to agentkit.agent.run_agent)
# ---------------------------------------------------------------------------

def _make_routed_client(backend: str | None, difficulty: str) -> Any:
    """Build the agentkit ``LLMClient`` for this run (lab routing on top).

    Difficulty routing picks the model; ``backend`` forces a specific endpoint.
    ``OMLXClient`` is an OpenAI-compatible adapter, so it serves any of the lab's
    backends (oMLX :8000 / VibeProxy :8317) by base_url + model.
    """
    from backends.adapter import BACKENDS, OMLXClient

    route_decision = route(difficulty)
    effective_backend = backend or route_decision.backend
    cfg = BACKENDS[effective_backend]
    # Honor the routed model unless the caller forced a different backend (where
    # the routed model may not exist; fall back to that backend's default).
    model = route_decision.model if backend is None else cfg["model"]
    return OMLXClient(model=model, base_url=cfg["base_url"])


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
    Run the ReAct agent on a single task (delegated to agentkit's loop).

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
        log:             When True, write a durable JSONL run log (replay substrate).

    Returns:
        AgentResult with answer, full trajectory, and metadata.
    """
    max_r = max_rounds or settings.agent_max_rounds
    sys_prompt = system_override or system_prompt or _build_system_prompt()
    # Describe the lab tools in-prompt: the agentkit OMLXClient doesn't forward
    # the tools schema to the API, so the local model needs them here to emit the
    # text tool-call agentkit's loop parses.
    sys_prompt = f"{sys_prompt}{_tool_use_instructions()}"
    client = _make_routed_client(backend, difficulty)

    # Optional durable run log (observability + replay substrate). Off by default
    # so the test suite doesn't litter logs/; scripts/go turns it on.
    logger = None
    if log:
        import uuid
        from agent.runlog import RunLogger
        logger = RunLogger(run_id=uuid.uuid4().hex[:8])
        logger.run_start(task, backend or route(difficulty).backend, getattr(client, "model", ""))

    # Delegate the loop. agentkit appends memory context, runs the structured +
    # text tool-call paths, and quarantines untrusted tool output internally.
    ak = _agentkit_run_agent(
        task,
        client,
        tools=_LabToolRegistry(),
        system_prompt=sys_prompt,
        max_rounds=max_r,
        memory=memory,
    )

    # Map agentkit's result back onto the lab's dataclasses (field-identical).
    trajectory = [
        TrajectoryStep(
            round_num=s.round_num,
            role=s.role,
            content=s.content,
            tool_name=s.tool_name,
            tool_args=dict(s.tool_args or {}),
            tool_result=dict(s.tool_result or {}),
        )
        for s in ak.trajectory
    ]

    if logger is not None:
        for s in trajectory:
            logger.step(s.round_num, s.role, s.content,
                        tool_name=s.tool_name, tool_args=s.tool_args)
        logger.run_end(ak.answer, ak.success, ak.stop_reason, len(trajectory),
                       total_usage={"total_tokens": getattr(ak, "total_tokens", 0)})

    return AgentResult(
        task=ak.task,
        answer=ak.answer,
        trajectory=trajectory,
        success=ak.success,
        rounds_used=len(trajectory),
        stop_reason=ak.stop_reason,
    )
