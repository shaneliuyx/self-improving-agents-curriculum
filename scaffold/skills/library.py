"""
skills/library.py - Skill acquisition, curation, and retrieval.

A "skill" is a reusable, validated procedure the agent has learned from past
trajectories. Skills are saved as paired files under skills/SKILLS/:
  <name>.md   - human-readable description and usage notes
  <name>.json - structured metadata: name, trigger, steps, eval_score

THIS IS A FACADE OVER agentkit. The propose -> verify -> save -> retrieve
machinery is NOT hand-rolled here: ``propose_skill`` / ``save_skill`` /
``load_skill`` / ``list_skills`` / ``search_skills`` delegate to an
``agentkit.skills.SkillLibrary`` (gate-verified persistence + semantic retrieval
over an injected ``Embedder``). The one lab-specific bit kept on top is the
lab's ``Skill`` SHAPE: the lab models a skill as ordered ``steps: list[str]``
(Module 06's teaching model), whereas agentkit's ``Skill`` carries a single
``body: str``. That is the gap this facade bridges - lab ``steps`` are mapped to
and from agentkit's ``body`` (newline-joined) on every save/load, so the lab's
public ``Skill`` keeps its ``steps`` field while persistence runs on agentkit.

Reference: SkillOS (https://arxiv.org/abs/2605.06614) and
Muse-Autoskill (https://arxiv.org/abs/2605.27366) show that curated skill
libraries outperform raw retrieval-augmented generation for agent tasks.
agentkit's ``skills`` layer ports the SkillOpt loop (microsoft/SkillOpt, MIT).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from config import settings

from agentkit.skills import Skill as _AgentkitSkill, SkillLibrary


# ---------------------------------------------------------------------------
# Data structure (the lab's STEPS-based Skill - the one lab-specific shape)
# ---------------------------------------------------------------------------

@dataclass
class Skill:
    """A reusable, validated agent skill.

    The lab models a skill as ordered ``steps`` (Module 06). agentkit models it
    as a single ``body`` string; ``_to_agentkit`` / ``_from_agentkit`` bridge the
    two so persistence and retrieval run on ``agentkit.skills.SkillLibrary`` while
    this dataclass keeps the lab's teaching shape.
    """
    name:        str
    description: str
    trigger:     str          # natural-language description of when to use this skill
    steps:       list[str]    # ordered list of steps
    eval_score:  float = 0.0  # score on the eval set when this skill was validated
    created_at:  float = field(default_factory=time.time)
    source_task: str = ""     # the task that generated this skill

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Skill":
        # Accept both the lab shape (``steps``) and the agentkit shape (``body``)
        # so a skill saved through agentkit's SkillLibrary loads back cleanly.
        if "steps" in data:
            steps = list(data["steps"])
        else:
            body = str(data.get("body", ""))
            steps = body.split("\n") if body else []
        return cls(
            name        = data["name"],
            description = data.get("description", ""),
            trigger     = data.get("trigger", ""),
            steps       = steps,
            eval_score  = float(data.get("eval_score", 0.0)),
            created_at  = float(data.get("created_at", 0.0)),
            source_task = data.get("source_task", ""),
        )

    # -- agentkit bridge ---------------------------------------------------

    def _to_agentkit(self) -> _AgentkitSkill:
        """Map this lab Skill onto an ``agentkit.skills.Skill`` (steps -> body)."""
        return _AgentkitSkill(
            name        = self.name,
            description = self.description,
            body        = "\n".join(self.steps),
            trigger     = self.trigger,
            eval_score  = self.eval_score,
            created_at  = self.created_at,
            source_task = self.source_task,
        )

    @classmethod
    def _from_agentkit(cls, sk: _AgentkitSkill) -> "Skill":
        """Map an ``agentkit.skills.Skill`` back onto the lab Skill (body -> steps)."""
        return cls(
            name        = sk.name,
            description = sk.description,
            trigger     = sk.trigger,
            steps       = sk.body.split("\n") if sk.body else [],
            eval_score  = sk.eval_score,
            created_at  = sk.created_at,
            source_task = sk.source_task,
        )


# ---------------------------------------------------------------------------
# agentkit SkillLibrary wiring (the operator-side seam)
# ---------------------------------------------------------------------------

def _embedder() -> Any:
    """The injected ``Embedder`` agentkit's retrieval ranks with.

    The lab's ``memory.store.OMLXEmbedder`` already satisfies agentkit's
    ``Embedder`` protocol (it is what ``lab_agent`` wires). Retrieval degrades to
    substring matching inside agentkit if the embedder call fails, so a missing
    backend never breaks the loop.
    """
    from memory.store import OMLXEmbedder
    return OMLXEmbedder()


def _library() -> SkillLibrary:
    """Build the ``SkillLibrary`` over the lab's configured skills directory."""
    settings.skills_dir.mkdir(parents=True, exist_ok=True)
    return SkillLibrary(_embedder(), settings.skills_dir)


# ---------------------------------------------------------------------------
# Propose (delegates to SkillLibrary.propose)
# ---------------------------------------------------------------------------

def propose_skill(
    trajectory_summary: str,
    source_task: str = "",
) -> Skill | None:
    """
    Ask the LLM to extract a reusable skill from a task trajectory.

    Delegates to ``agentkit.skills.SkillLibrary.propose`` (the injected
    ``LLMClient`` is the lab's ``OMLXClient``); the returned agentkit Skill is
    mapped back to the lab's steps-based shape. Returns None when nothing
    generalizable was found (a proposal miss never raises).

    Args:
        trajectory_summary: Text summary of the trajectory (from agent/loop.py).
        source_task:        The original task string (for metadata).

    Returns:
        A Skill object if one was extracted, or None.
    """
    from backends.adapter import OMLXClient

    proposed = _library().propose(OMLXClient(), trajectory_summary, source_task=source_task)
    return Skill._from_agentkit(proposed) if proposed is not None else None


# ---------------------------------------------------------------------------
# Save / load / list (delegate to SkillLibrary.save / load / list)
# ---------------------------------------------------------------------------

def save_skill(skill: Skill) -> Path:
    """
    Persist a validated skill via ``agentkit.skills.SkillLibrary.save`` as paired
    .json + .md files under skills/SKILLS/.

    Args:
        skill: The Skill to save (should have passed the verification gate).

    Returns:
        Path to the saved .json file.
    """
    return _library().save(skill._to_agentkit())


def load_skill(name: str) -> Skill | None:
    """Load a skill by name via agentkit's SkillLibrary, mapped to the lab shape."""
    loaded = _library().load(name)
    return Skill._from_agentkit(loaded) if loaded is not None else None


def list_skills() -> list[str]:
    """Return the names of all saved skills (delegated to SkillLibrary.list)."""
    return _library().list()


# ---------------------------------------------------------------------------
# Search (delegates to SkillLibrary.retrieve)
# ---------------------------------------------------------------------------

def search_skills(query: str, top_k: int = 3) -> list[Skill]:
    """
    Search for skills by semantic similarity via ``SkillLibrary.retrieve``
    (local oMLX embeddings; agentkit degrades to keyword matching on failure).

    Args:
        query:  Natural language description of what you need.
        top_k:  Maximum number of skills to return.

    Returns:
        List of Skill objects sorted by relevance.
    """
    return [Skill._from_agentkit(s) for s in _library().retrieve(query, k=top_k)]
