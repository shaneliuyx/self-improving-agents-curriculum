"""
Checkpoint and rollback helper for self-modifying agent loops.
Usage:
    sha = checkpoint("pre-mutation-5")      # snapshot
    ...mutation happens...
    if not verify():
        rollback(sha)                       # undo everything
"""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CheckpointStore:
    history: list[tuple[str, str]] = field(default_factory=list)  # (tag, sha)

    def checkpoint(self, tag: str) -> str:
        """Commit the current working tree state and record the SHA."""
        # Stage all tracked files
        subprocess.run(["git", "add", "-u"], check=True, capture_output=True)

        # If nothing to commit, record existing HEAD
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True
        ).stdout.strip()
        if not status:
            sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True
            ).stdout.strip()
        else:
            subprocess.run(
                ["git", "commit", "-m", f"checkpoint: {tag}"],
                check=True, capture_output=True
            )
            sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True
            ).stdout.strip()

        self.history.append((tag, sha))
        print(f"[checkpoint] {tag} -> {sha[:8]}")
        return sha

    def rollback(self, sha: str) -> None:
        """Hard-reset working tree to the given SHA."""
        subprocess.run(
            ["git", "reset", "--hard", sha],
            check=True, capture_output=True
        )
        print(f"[rollback] reset to {sha[:8]}")

    def latest(self) -> tuple[str, str] | None:
        return self.history[-1] if self.history else None
