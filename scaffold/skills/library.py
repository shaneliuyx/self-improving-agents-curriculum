"""
skills/library.py - Skill acquisition, curation, and retrieval.

A "skill" is a reusable, validated procedure the agent has learned from past
trajectories. Skills are saved as paired files under skills/SKILLS/:
  <name>.md   - human-readable description and usage notes
  <name>.json - structured metadata: name, trigger, steps, eval_score

The propose -> verify -> save pipeline ensures no unvalidated skill enters
the library. Skills are retrieved by semantic similarity (same embedding
approach as memory/store.py).

Reference: SkillOS (https://arxiv.org/abs/2605.06614) and
Muse-Autoskill (https://arxiv.org/abs/2605.27366) show that curated skill
libraries outperform raw retrieval-augmented generation for agent tasks.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from backends.adapter import chat
from backends.router import route
from config import settings


# ---------------------------------------------------------------------------
# Data structure
# ---------------------------------------------------------------------------

@dataclass
class Skill:
    """A reusable, validated agent skill."""
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
        return cls(
            name        = data["name"],
            description = data["description"],
            trigger     = data["trigger"],
            steps       = data["steps"],
            eval_score  = data.get("eval_score", 0.0),
            created_at  = data.get("created_at", 0.0),
            source_task = data.get("source_task", ""),
        )


# ---------------------------------------------------------------------------
# Skill proposal prompt
# ---------------------------------------------------------------------------

_PROPOSE_SYSTEM = """\
You are a skill extraction engine for a self-improving agent.

Given a successful task trajectory, extract ONE reusable skill the agent
demonstrated. Return ONLY valid JSON:

{
  "name":        "<snake_case_identifier, max 40 chars>",
  "description": "<one paragraph>",
  "trigger":     "<natural language: when should an agent use this skill?>",
  "steps":       ["step 1", "step 2", "..."]
}

Rules:
- The skill must generalise beyond this specific task.
- Steps must be concrete and actionable.
- If the trajectory shows no reusable skill, return {"name": "none"}.
"""


# ---------------------------------------------------------------------------
# Propose
# ---------------------------------------------------------------------------

def propose_skill(
    trajectory_summary: str,
    source_task: str = "",
) -> Skill | None:
    """
    Ask the LLM to extract a reusable skill from a task trajectory.

    Args:
        trajectory_summary: Text summary of the trajectory (from agent/loop.py).
        source_task:        The original task string (for metadata).

    Returns:
        A Skill object if one was extracted, or None if the trajectory
        demonstrates no generalizable skill.
    """
    route_decision = route("hard")
    messages = [
        {"role": "system", "content": _PROPOSE_SYSTEM},
        {
            "role": "user",
            "content": (
                "Extract a reusable skill from this trajectory:\n\n"
                f"{trajectory_summary}"
            ),
        },
    ]

    raw = chat(
        messages,
        backend=route_decision.backend,
        temperature=0.3,
        max_tokens=512,
    )

    return _parse_skill_proposal(raw, source_task)


def _parse_skill_proposal(raw: str, source_task: str) -> Skill | None:
    """Parse the LLM JSON response into a Skill. Returns None on failure or 'none' name."""
    text = raw.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None

    if data.get("name", "none").lower() == "none":
        return None

    # Sanitise name to a valid filename component
    name = re.sub(r"[^a-z0-9_]", "_", data.get("name", "skill").lower())[:40]

    return Skill(
        name        = name,
        description = str(data.get("description", "")),
        trigger     = str(data.get("trigger", "")),
        steps       = list(data.get("steps", [])),
        source_task = source_task,
    )


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def save_skill(skill: Skill) -> Path:
    """
    Persist a validated skill to skills/SKILLS/ as paired .json + .md files.

    Args:
        skill: The Skill to save (should have passed the verification gate).

    Returns:
        Path to the saved .json file.
    """
    skills_dir = settings.skills_dir
    skills_dir.mkdir(parents=True, exist_ok=True)

    json_path = skills_dir / f"{skill.name}.json"
    md_path   = skills_dir / f"{skill.name}.md"

    # Save structured metadata
    json_path.write_text(json.dumps(skill.to_dict(), indent=2), encoding="utf-8")

    # Save human-readable description
    md_content = (
        f"# Skill: {skill.name}\n\n"
        f"**Trigger:** {skill.trigger}\n\n"
        f"## Description\n\n{skill.description}\n\n"
        f"## Steps\n\n"
        + "\n".join(f"{i+1}. {s}" for i, s in enumerate(skill.steps))
        + f"\n\n---\n*Eval score: {skill.eval_score:.3f} | "
        f"Source: {skill.source_task[:80]}*\n"
    )
    md_path.write_text(md_content, encoding="utf-8")

    return json_path


# ---------------------------------------------------------------------------
# Load and search
# ---------------------------------------------------------------------------

def load_skill(name: str) -> Skill | None:
    """Load a skill by name from skills/SKILLS/<name>.json."""
    json_path = settings.skills_dir / f"{name}.json"
    if not json_path.exists():
        return None
    data = json.loads(json_path.read_text(encoding="utf-8"))
    return Skill.from_dict(data)


def list_skills() -> list[str]:
    """Return the names of all saved skills."""
    return [p.stem for p in sorted(settings.skills_dir.glob("*.json"))]


def search_skills(query: str, top_k: int = 3) -> list[Skill]:
    """
    Search for skills by semantic similarity using local oMLX embeddings.

    Falls back to keyword matching if the embedding server is unavailable.

    Args:
        query:  Natural language description of what you need.
        top_k:  Maximum number of skills to return.

    Returns:
        List of Skill objects sorted by relevance.
    """
    all_names = list_skills()
    if not all_names:
        return []

    skills = [s for name in all_names if (s := load_skill(name)) is not None]
    if not skills:
        return []

    # Try semantic search via embeddings
    try:
        from backends.adapter import embed
        import numpy as np

        query_vec = np.array(embed([query])[0], dtype=np.float32)
        trigger_texts = [s.trigger + " " + s.description for s in skills]
        skill_vecs = [np.array(v, dtype=np.float32) for v in embed(trigger_texts)]

        def cosine(a: np.ndarray, b: np.ndarray) -> float:
            na, nb = np.linalg.norm(a), np.linalg.norm(b)
            return float(np.dot(a, b) / (na * nb)) if na > 0 and nb > 0 else 0.0

        scored = sorted(
            zip(skills, skill_vecs),
            key=lambda x: cosine(query_vec, x[1]),
            reverse=True,
        )
        return [s for s, _ in scored[:top_k]]

    except Exception:
        # Embedding unavailable - fall back to simple keyword matching
        q_lower = query.lower()
        matched = [
            s for s in skills
            if q_lower in s.trigger.lower() or q_lower in s.description.lower()
        ]
        return matched[:top_k]
