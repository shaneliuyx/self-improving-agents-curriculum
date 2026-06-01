"""
agent/runlog.py - Durable per-step run logging (JSONL).

The trajectory in AgentResult lives in RAM and is lost when the process exits;
only a ~200-char memory summary and the prose CHANGELOG survive. That means you
cannot reconstruct what a past run actually did - which step called which tool,
with what args, what came back. This logger writes one JSON record per step to
an append-only logs/run-<ts>-<id>.jsonl file.

It is the shared substrate for two harness capabilities the article calls
first-class and most teams skip:
  - Observability: log-every-step, inspectable after the fact.
  - Replay (agent/replay.py): re-read a recorded run to debug a regression.

Append-only by design (immutable history = auditable). No external deps.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from config import settings


class RunLogger:
    """Append-only JSONL logger for one agent run.

    Each record is a flat dict with a `kind` discriminator: "run_start",
    "step", or "run_end". One file per run so concurrent runs never interleave.
    """

    def __init__(self, run_id: str, log_dir: Path | None = None, clock: float | None = None) -> None:
        # clock is injectable so tests/replay are deterministic (no wall-clock
        # in the filename when a caller wants reproducibility).
        ts = clock if clock is not None else time.time()
        self.run_id = run_id
        base = log_dir or (settings.project_root / "logs")
        base.mkdir(parents=True, exist_ok=True)
        # integer seconds keep the filename stable + sortable
        self.path = base / f"run-{int(ts)}-{run_id}.jsonl"

    def _write(self, record: dict[str, Any]) -> None:
        record.setdefault("ts", time.time())
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")

    def run_start(self, task: str, backend: str, model: str) -> None:
        self._write({"kind": "run_start", "run_id": self.run_id,
                     "task": task, "backend": backend, "model": model})

    def step(self, round_num: int, role: str, content: str,
             tool_name: str = "", tool_args: dict | None = None,
             usage: dict | None = None) -> None:
        """One trajectory step. `usage` carries token telemetry (prompt/
        completion/total) when the backend returned response.usage."""
        self._write({
            "kind": "step", "round": round_num, "role": role,
            "content": content[:2000],          # cap; full output is huge
            "tool_name": tool_name, "tool_args": tool_args or {},
            "usage": usage or {},
        })

    def run_end(self, answer: str, success: bool, stop_reason: str,
                rounds_used: int, total_usage: dict | None = None) -> None:
        self._write({"kind": "run_end", "answer": answer[:2000],
                     "success": success, "stop_reason": stop_reason,
                     "rounds_used": rounds_used, "total_usage": total_usage or {}})


def usage_to_dict(usage: Any) -> dict[str, int]:
    """Normalize an OpenAI `response.usage` object (or None) to a plain dict
    of prompt/completion/total tokens. Safe on backends that omit usage."""
    if usage is None:
        return {}
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
    }
