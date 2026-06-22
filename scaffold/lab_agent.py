"""
lab_agent.py - the lab's self-improving agent, BUILT ON agentkit.

This is the canonical entry point: the lab's agent IS agentkit's
``SelfImprovingAgent`` facade, wired with the lab's operator-side adapters and
its eval task. Nothing here re-implements the loop - the whole self-improving
machinery (config-driven roles + memory + gated evolve + skills + forge_tool)
lives in agentkit; this file only COMPOSES it for the lab:

  * backend  = ``backends.adapter.OMLXClient``  (agentkit LLMClient over oMLX)
  * embedder = ``memory.store.OMLXEmbedder``    (agentkit Embedder over oMLX)
  * memory   = a ``MemoryStore`` at ``settings.memory_db_path``
  * config   = ``settings.project_root / "agent_config"`` (roles/ + skills/)
  * eval set = derived from ``evals/tasks.py`` for the gated ``improve`` loop

Run:
    # one task through the agent (needs oMLX on :8000)
    python -m lab_agent
    # one task + one gated self-improvement epoch
    python -m lab_agent --improve

The improve loop rewrites the chosen role's config FILE on disk only when a
strictly-better variant passes agentkit's LEARN gate - review it as a git diff.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from agentkit import SelfImprovingAgent

from backends.adapter import OMLXClient
from config import settings
from evals.tasks import TASKS
from memory.store import OMLXEmbedder

# The lab's policy folder (agentkit reads roles/ and skills/ under it; if roles/
# is absent it falls back to agentkit's shipped default ensemble, and improve()
# materializes an improved role here on first accept).
LAB_CONFIG_DIR: Path = settings.project_root / "agent_config"

# A representative task to demo a single run.
DEMO_TASK = "What is 17 * 23? Use the calculator tool."


def lab_eval_set() -> list[tuple[str, str]]:
    """Derive agentkit's ``(task, expected_substring)`` eval set from evals/tasks.py.

    agentkit's ``improve`` builds a deterministic substring-recall evaluator from
    ``(task, expected)`` pairs. The lab's ``Task`` carries a *checker function*
    rather than a plain expected string, so we map the deterministic, single-token
    tasks to their expected substring. This is the lab-specific glue that
    connects ``evals/`` to agentkit's gated optimizer.
    """
    # The expected substring for each deterministic task id (anchors the gate).
    expected: dict[str, str] = {
        "arith_01": "391",
        "arith_02": "264",
        "arith_03": "1024",
        "reason_01": "150",
        "reason_02": "11",
    }
    pairs: list[tuple[str, str]] = []
    for task in TASKS:
        exp = expected.get(task.id)
        if exp is not None:
            pairs.append((task.input, exp))
    return pairs


def build_lab_agent(
    backend: Any | None = None,
    *,
    with_memory: bool = True,
    config_dir: str | Path | None = None,
) -> SelfImprovingAgent:
    """Compose the lab's ``SelfImprovingAgent`` on agentkit.

    Args:
        backend:     an agentkit ``LLMClient``. Defaults to an ``OMLXClient``
                     (real oMLX). Pass a fake client to compose this OFFLINE.
        with_memory: when True, wire a ``MemoryStore`` (needs the oMLX embedder).
        config_dir:  the policy folder; defaults to ``LAB_CONFIG_DIR``.

    Returns:
        A wired ``agentkit.SelfImprovingAgent`` - the lab agent.
    """
    client = backend or OMLXClient()
    cfg = Path(config_dir) if config_dir is not None else LAB_CONFIG_DIR
    cfg.mkdir(parents=True, exist_ok=True)

    embedder = OMLXEmbedder() if with_memory else None
    memory_path = settings.memory_db_path if with_memory else None

    return SelfImprovingAgent.from_config(
        cfg,
        backend=client,
        embedder=embedder,
        memory_path=memory_path,
    )


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    do_improve = "--improve" in argv

    agent = build_lab_agent()
    print(f"lab agent on agentkit  config={LAB_CONFIG_DIR}")
    print(f"roles loaded: {sorted(agent.roles)}")

    result = agent.run(DEMO_TASK)
    print(f"\n[run] task: {DEMO_TASK}")
    print(f"[run] answer: {result.answer!r}")
    print(f"[run] stop={result.stop_reason} rounds={len(result.trajectory)}")

    if do_improve:
        eval_set = lab_eval_set()
        role = next(iter(agent.roles))
        print(f"\n[improve] gated evolve of role {role!r} over {len(eval_set)} eval pairs")
        opt = agent.improve(eval_set, role=role, epochs=2)
        print(f"[improve] delta={opt.delta:+.3f}  best kept on disk only if delta>0")

    return 0


if __name__ == "__main__":
    sys.exit(main())
