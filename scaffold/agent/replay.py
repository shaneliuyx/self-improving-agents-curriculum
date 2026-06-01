"""
agent/replay.py - Time-travel debugging over a recorded run.

The article calls replay/debug a first-class harness layer most teams skip.
"Replay" in the eval sense (notes 07/10) means re-running the TASK SET; this is
different - it reads ONE recorded trajectory (the JSONL written by
agent/runlog.py) and lets you step through exactly what a single past run did.

For a self-improving agent this is high-value: when a self-modification helps
or hurts, you want to replay the exact trajectory that produced the result -
which step called which tool, with what args, what came back, and the token
cost - rather than guess from a one-line CHANGELOG entry.

Two modes:
  pretty(path)         - human-readable step-by-step dump for debugging.
  load(path)           - structured records (list[dict]) for programmatic use.

No external deps. Read-only: replay never mutates state or calls the LLM, so it
is always safe to run against a production log.

CLI:
  python -m agent.replay logs/run-<ts>-<id>.jsonl
  python -m agent.replay --latest          # replay the most recent run log
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from config import settings


def load(path: str | Path) -> list[dict]:
    """Load a run log as a list of records (run_start, step*, run_end)."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"run log not found: {p}")
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def latest_log(log_dir: Path | None = None) -> Path | None:
    """Return the most recent run log, or None if none exist."""
    base = log_dir or (settings.project_root / "logs")
    logs = sorted(base.glob("run-*.jsonl"))
    return logs[-1] if logs else None


def pretty(path: str | Path) -> str:
    """Render a recorded run as a readable step-by-step trace."""
    records = load(path)
    out: list[str] = [f"=== REPLAY: {Path(path).name} ==="]
    for r in records:
        kind = r.get("kind")
        if kind == "run_start":
            out.append(f"START  task={r.get('task','')!r}  backend={r.get('backend')}  model={r.get('model')}")
        elif kind == "step":
            tool = r.get("tool_name") or ""
            if tool:
                out.append(f"  [r{r.get('round')}] {r.get('role')} -> {tool}({r.get('tool_args', {})})")
                out.append(f"           => {r.get('content','')[:160]}")
            else:
                out.append(f"  [r{r.get('round')}] {r.get('role')}: {r.get('content','')[:160]}")
        elif kind == "run_end":
            usage = r.get("total_usage", {})
            out.append(f"END    success={r.get('success')}  stop={r.get('stop_reason')}  "
                       f"rounds={r.get('rounds_used')}  tokens={usage.get('total_tokens', '?')}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if args and args[0] == "--latest":
        target = latest_log()
        if target is None:
            print("no run logs found in logs/", file=sys.stderr)
            return 1
    elif args:
        target = Path(args[0])
    else:
        print(__doc__)
        return 0
    print(pretty(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
