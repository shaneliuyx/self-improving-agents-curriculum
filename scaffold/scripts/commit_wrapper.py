"""
Safe-commit wrapper: snapshot -> stage -> commit -> tag.
Called by the agent harness, never directly by the LLM.
"""

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CHANGELOG = Path("CHANGELOG.md")
VERIFICATION_DIR = Path("verification")

def run(cmd: list[str], check: bool = True) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, check=check)
    return result.stdout.strip()

def safe_commit(message: str, tag: str | None = None) -> str:
    """
    Stage all tracked changes, commit, and optionally tag.
    Returns the new commit SHA.
    Raises on any git failure so the harness can roll back.
    """
    # Guard: verification directory must not have unstaged changes
    diff = run(["git", "diff", "--name-only", str(VERIFICATION_DIR)], check=False)
    if diff:
        raise RuntimeError(
            f"Verification directory has unstaged changes: {diff}\n"
            "Self-modification must not alter verification gates."
        )

    # Append to CHANGELOG
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entry = f"\n## {ts}\n{message}\n"
    with CHANGELOG.open("a") as f:
        f.write(entry)

    run(["git", "add", "-u"])
    run(["git", "add", str(CHANGELOG)])
    run(["git", "commit", "-m", message])
    sha = run(["git", "rev-parse", "HEAD"])

    if tag:
        run(["git", "tag", tag])
        print(f"Tagged {tag} at {sha[:8]}", file=sys.stderr)

    print(f"Committed {sha[:8]}: {message}", file=sys.stderr)
    return sha


if __name__ == "__main__":
    # CLI usage: python scripts/commit_wrapper.py "message" [tag]
    msg = sys.argv[1] if len(sys.argv) > 1 else "agent: automated mutation"
    tg = sys.argv[2] if len(sys.argv) > 2 else None
    print(safe_commit(msg, tg))
