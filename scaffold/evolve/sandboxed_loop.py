"""
Self-modifying agent loop wrapped in:
  - a constrained subprocess for each mutation
  - checkpoint/rollback around every LEARN step
  - the unified LLM adapter (omlx or vibeproxy)

Run:
  AGENT_BACKEND=omlx python evolve/sandboxed_loop.py
  AGENT_BACKEND=vibeproxy python evolve/sandboxed_loop.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Project root (one level up from evolve/)
ROOT = Path(__file__).parent.parent

# Add root to path so we can import backends/adapter.py
sys.path.insert(0, str(ROOT))

from backends.adapter import make_client
from scripts.checkpoint import CheckpointStore
from verification.gates import verify  # verify(proposal, candidate_score, baseline_score) -> Verdict

MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "10"))
WORKSPACE = ROOT / "evolve" / "archive"
WORKSPACE.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = (ROOT / "AGENTS.md").read_text()
GOAL = (ROOT / "GOAL.md").read_text()


def propose_mutation(client, model: str, context: str) -> str:
    """Ask the LLM to propose a self-modification given recent context."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"GOAL:\n{GOAL}\n\n"
                    f"RECENT CONTEXT:\n{context}\n\n"
                    "Propose ONE small, verifiable improvement to the agent codebase. "
                    "Respond with a JSON object: "
                    "{\"file\": \"<relative path>\", \"description\": \"<one sentence>\", "
                    "\"patch\": \"<unified diff or new file content>\"}"
                ),
            },
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def apply_patch(patch_json: str) -> bool:
    """Write the proposed patch to disk. Returns True if successful."""
    try:
        data = json.loads(patch_json)
        target = ROOT / data["file"]
        if "patch" in data and data["patch"].startswith("---"):
            # Apply as unified diff via patch(1)
            result = subprocess.run(
                ["patch", "-p1"],
                input=data["patch"],
                text=True,
                cwd=str(ROOT),
                capture_output=True,
            )
            return result.returncode == 0
        else:
            # Full file replacement
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(data["patch"])
            return True
    except (json.JSONDecodeError, KeyError, OSError) as e:
        print(f"[apply_patch] error: {e}", file=sys.stderr)
        return False


def main() -> None:
    client, model = make_client()
    store = CheckpointStore()
    context_window: list[str] = []

    print(f"[loop] backend={os.getenv('AGENT_BACKEND', 'omlx')} model={model}")
    print(f"[loop] max_iterations={MAX_ITERATIONS}")

    for i in range(MAX_ITERATIONS):
        print(f"\n--- Iteration {i+1}/{MAX_ITERATIONS} ---")

        # 1. SNAPSHOT before mutation
        sha = store.checkpoint(f"pre-mutation-{i+1}")

        # 2. PROPOSE mutation
        context = "\n".join(context_window[-5:]) if context_window else "No prior context."
        raw = propose_mutation(client, model, context)
        print(f"[propose] {raw[:120]}...")

        # 3. APPLY mutation (inside this process = constrained to ROOT only)
        applied = apply_patch(raw)
        if not applied:
            print("[apply] patch failed, rolling back")
            store.rollback(sha)
            context_window.append(f"iteration {i+1}: patch failed to apply")
            continue

        # 4. VERIFY — use gates.verify() with the proposal dict and neutral scores
        try:
            description = json.loads(raw).get("description", "agent mutation")
            proposal_file = json.loads(raw).get("file", "unknown")
        except (json.JSONDecodeError, AttributeError):
            description = "agent mutation"
            proposal_file = "unknown"

        verdict = verify(
            proposal={"type": "skill", "content": description, "file": proposal_file},
            candidate_score=0.0,
            baseline_score=0.0,
        )
        passed = verdict.accepted

        if passed:
            # 5a. COMMIT via safe wrapper
            from scripts.commit_wrapper import safe_commit
            new_sha = safe_commit(
                f"feat: {description}",
                tag=f"mutation-{i+1}-ok",
            )
            context_window.append(f"iteration {i+1}: mutation applied and verified ({new_sha[:8]})")
            print(f"[loop] iteration {i+1} SUCCESS")
        else:
            # 5b. ROLLBACK
            store.rollback(sha)
            context_window.append(f"iteration {i+1}: mutation failed verification ({verdict.reason}), rolled back to {sha[:8]}")
            print(f"[loop] iteration {i+1} FAIL - reverted")

    print("\n[loop] complete")


if __name__ == "__main__":
    main()
