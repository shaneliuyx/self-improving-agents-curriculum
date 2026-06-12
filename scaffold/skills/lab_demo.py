"""
skills/lab_demo.py - hands-on skill lifecycle demo (Module 06).

Walks one skill through the lifecycle: propose (from a successful trajectory) ->
validate -> dedupe-check -> store -> retrieve. Uses the real skills.library API,
where a Skill is a structured set of STEPS (name / description / trigger / steps),
not raw code.

Run from the scaffold root:
  AGENT_BACKEND=omlx     python skills/lab_demo.py
  AGENT_BACKEND=vibeproxy python skills/lab_demo.py

Generation respects AGENT_BACKEND; embeddings used by search_skills are always
local (oMLX), per the curriculum's embeddings-stay-local rule.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skills.library import propose_skill, save_skill, search_skills, list_skills, Skill

# A minimal successful trajectory to propose a skill from.
EXAMPLE_TRAJECTORY = """
TASK: Count word frequencies in a text string.
SOLUTION:
  - lowercase the text and split on whitespace
  - tally occurrences with collections.Counter
  - return the tallies as a dict
TEST: word_freq("the cat sat on the mat")
RESULT: {"the": 2, "cat": 1, "sat": 1, "on": 1, "mat": 1}
STATUS: SUCCESS
"""


def _is_valid(skill: Skill | None) -> bool:
    """A proposal is usable if it named a real, generalizable skill with steps."""
    return skill is not None and skill.name.lower() != "none" and bool(skill.steps)


def run() -> None:
    print("[lab] proposing a skill from the example trajectory...")
    skill = propose_skill(EXAMPLE_TRAJECTORY, source_task="count_word_frequencies")

    if not _is_valid(skill):
        print("[lab] no reusable skill was proposed - discarding.")
        return

    print(f"[lab] proposed: {skill.name}")
    print(f"[lab]   trigger: {skill.trigger}")
    print(f"[lab]   steps:   {skill.steps}")

    # Curate before storing: skip if a near-identical skill already exists.
    similar = search_skills(skill.trigger, top_k=1)
    if similar and similar[0].name == skill.name:
        print(f"[lab] '{skill.name}' already in the library - skipping store (dedupe).")
    else:
        path = save_skill(skill)
        print(f"[lab] stored skill -> {path}")

    # Retrieve test: can we find it by a paraphrased need?
    results = search_skills("count how often each word appears in a string", top_k=2)
    print(f"[lab] retrieved: {[s.name for s in results]}")
    print(f"[lab] library now holds: {list_skills()}")


if __name__ == "__main__":
    run()
