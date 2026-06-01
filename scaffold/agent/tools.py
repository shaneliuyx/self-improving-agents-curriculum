"""
agent/tools.py - Tool registry for the ReAct agent.

Each tool has:
  - A JSON schema (passed to the LLM as a function definition)
  - A Python implementation
  - Registration in TOOL_SCHEMAS and TOOL_IMPLS

Tools provided here are intentionally minimal and safe:
  1. calculator  - evaluate a simple arithmetic expression (no exec/eval on arbitrary code)
  2. read_file   - read a text file relative to the project root (sandboxed)

To add a tool: add its schema to TOOL_SCHEMAS and its implementation to TOOL_IMPLS,
then it is automatically available to the agent loop.
"""

from __future__ import annotations

import ast
import operator
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Safe arithmetic evaluator (no exec / eval on arbitrary code)
# ---------------------------------------------------------------------------
_SAFE_OPS = {
    ast.Add:  operator.add,
    ast.Sub:  operator.sub,
    ast.Mult: operator.mul,
    ast.Div:  operator.truediv,
    ast.Pow:  operator.pow,
    ast.Mod:  operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(expr: str) -> float:
    """
    Evaluate a simple arithmetic expression string safely.
    Raises ValueError for unsupported operations.
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid expression: {expr!r}") from exc
    return _eval_node(tree.body)


def _eval_node(node: ast.expr) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"Unsupported constant type: {type(node.value)}")
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        return _SAFE_OPS[op_type](left, right)
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        return _SAFE_OPS[op_type](_eval_node(node.operand))
    raise ValueError(f"Unsupported AST node: {type(node).__name__}")


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).parent.parent

# Capability scoping (the L1-prose -> L2-enforced move). Writes to these dirs
# are refused even though they live under the project root: the agent must not
# rewrite its own verifier, git history, or driver scripts.
_FORBIDDEN_WRITE_DIRS = {"verification", "scripts", ".git", "evals"}


def _resolve_within_project(path: str) -> Path:
    """Resolve `path` under the project root, raising PermissionError if it
    escapes. Uses Path.parents membership (not str.startswith, which lets a
    sibling dir whose name is a prefix slip through)."""
    abs_root = _PROJECT_ROOT.resolve()
    abs_path = (abs_root / path).resolve()
    if abs_path != abs_root and abs_root not in abs_path.parents:
        raise PermissionError(f"path escapes project root: {path!r}")
    return abs_path


def _assert_writable(path: str) -> Path:
    """Resolve under project root AND enforce the write-allowlist. Raises
    PermissionError on escape or a forbidden self-modification dir. Call this
    BEFORE reading/editing a file so a forbidden path is denied by-path before
    it is touched by-content (defense in depth)."""
    abs_path = _resolve_within_project(path)
    abs_root = _PROJECT_ROOT.resolve()
    rel_parts = abs_path.relative_to(abs_root).parts
    if rel_parts and rel_parts[0] in _FORBIDDEN_WRITE_DIRS:
        raise PermissionError(
            f"write denied: {rel_parts[0]}/ is capability-scoped off-limits "
            f"(agent may not modify its own verifier/scripts/git)"
        )
    return abs_path


def _safe_write(path: str, content: str) -> Path:
    """Capability-scoped, atomic write. Refuses paths outside the project root
    and writes into the forbidden self-modification dirs. Writes via a temp
    file + os.replace so a crash mid-write never leaves a half-written file."""
    abs_path = _assert_writable(path)
    fd, tmp = tempfile.mkstemp(dir=str(abs_path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, abs_path)   # atomic on POSIX
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return abs_path


def _tool_calculator(expression: str) -> dict[str, Any]:
    """Evaluate a simple arithmetic expression. Returns the numeric result."""
    try:
        result = _safe_eval(expression)
        return {"result": result, "expression": expression}
    except (ValueError, ZeroDivisionError) as exc:
        return {"error": str(exc), "expression": expression}


def _tool_read_file(path: str) -> dict[str, Any]:
    """
    Read a text file relative to the project root.
    Only files inside the project directory are accessible (sandboxed).
    """
    # Resolve to an absolute path and verify it's inside the project root.
    # Uses Path.parents membership (not str.startswith, which lets a sibling
    # dir whose name is a prefix slip through).
    try:
        abs_path = _resolve_within_project(path)
        abs_root = _PROJECT_ROOT.resolve()
    except PermissionError:
        return {"error": "Access denied: path is outside the project directory"}
    except Exception as exc:
        return {"error": f"Path resolution failed: {exc}"}

    # Never surface secrets: refuse to read dotenv / key files even within root.
    if abs_path.name in {".env", ".env.local"} or abs_path.suffix in {".pem", ".key"}:
        return {"error": "Access denied: secret file"}

    if not abs_path.exists():
        return {"error": f"File not found: {path}"}

    if not abs_path.is_file():
        return {"error": f"Not a file: {path}"}

    try:
        content = abs_path.read_text(encoding="utf-8")
        # Truncate to 4000 chars to keep context manageable
        truncated = len(content) > 4000
        return {
            "content": content[:4000],
            "truncated": truncated,
            "path": str(abs_path.relative_to(abs_root)),
        }
    except OSError as exc:
        return {"error": f"Could not read file: {exc}"}


def _tool_edit_file(path: str, old_str: str, new_str: str) -> dict[str, Any]:
    """
    Apply an anchored edit: replace `old_str` with `new_str` in `path`.
    This is the structured-diff discipline (NOT full-file overwrite, which
    fails on large files): the model supplies a unique anchor, the harness
    applies it atomically and can roll back. Contract:
      - `old_str` MUST match exactly once (0 = anchor not found; >1 = ambiguous).
      - write is atomic (temp + os.replace) and capability-scoped (_safe_write).
      - returns the snapshot of the prior content so the caller (recovery loop)
        can restore on a downstream failure.
    """
    # Deny-by-path BEFORE touch-by-content: a forbidden file must not even be
    # read for anchor-counting (defense in depth).
    try:
        abs_path = _assert_writable(path)
    except PermissionError as exc:
        return {"error": str(exc)}
    if not abs_path.is_file():
        return {"error": f"File not found: {path}"}
    original = abs_path.read_text(encoding="utf-8")
    count = original.count(old_str)
    if count == 0:
        return {"error": f"anchor not found: old_str does not appear in {path}"}
    if count > 1:
        return {"error": f"ambiguous anchor: old_str appears {count}x in {path}; make it unique"}
    updated = original.replace(old_str, new_str, 1)
    try:
        _safe_write(path, updated)
    except PermissionError as exc:
        return {"error": str(exc)}
    return {"ok": True, "path": path, "snapshot": original}


def _tool_run_tests(test_path: str = "evals/tests") -> dict[str, Any]:
    """
    Run pytest on a path inside the project and return pass/fail + tail of output.
    This is the VERIFY half of the write->verify->recover chain: after an
    edit_file the agent runs this, and on failure feeds the captured output
    back into its next turn (recovery). 60s timeout; capability-scoped path.
    """
    try:
        abs_path = _resolve_within_project(test_path)
    except PermissionError as exc:
        return {"error": str(exc)}
    try:
        proc = subprocess.run(
            ["python", "-m", "pytest", str(abs_path), "-x", "-q"],
            capture_output=True, text=True, timeout=60, cwd=str(_PROJECT_ROOT),
        )
    except subprocess.TimeoutExpired:
        return {"passed": False, "error": "pytest timed out after 60s"}
    except FileNotFoundError:
        return {"passed": False, "error": "pytest not installed"}
    tail = (proc.stdout[-1500:] + proc.stderr[-500:]).strip()
    return {"passed": proc.returncode == 0, "output": tail}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TOOL_IMPLS: dict[str, Any] = {
    "calculator": _tool_calculator,
    "read_file":  _tool_read_file,
    "edit_file":  _tool_edit_file,
    "run_tests":  _tool_run_tests,
}

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": (
                "Evaluate a simple arithmetic expression and return the numeric result. "
                "Supports +, -, *, /, **, % and parentheses. No variables or functions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Arithmetic expression to evaluate, e.g. '(3 + 4) * 2'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the contents of a text file inside the project directory. "
                "Provide a path relative to the project root, e.g. 'GOAL.md' or 'evals/tasks.py'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file from the project root.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "Apply an anchored edit to a file: replace old_str with new_str. "
                "old_str MUST appear EXACTLY ONCE in the file (include enough "
                "surrounding context to make it unique). Prefer this over rewriting "
                "a whole file. The write is atomic and returns a snapshot for rollback."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path":    {"type": "string", "description": "Relative path from the project root."},
                    "old_str": {"type": "string", "description": "Exact unique text to replace (with context)."},
                    "new_str": {"type": "string", "description": "Replacement text."},
                },
                "required": ["path", "old_str", "new_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": (
                "Run pytest on a path inside the project and return pass/fail plus "
                "output. Use this after an edit to verify it; on failure, read the "
                "output and fix, then run again (the edit->test->fix recovery loop)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "test_path": {
                        "type": "string",
                        "description": "Relative path to a test file or dir. Default: 'evals/tests'.",
                    }
                },
                "required": [],
            },
        },
    },
]


def dispatch_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Dispatch a tool call by name with the given arguments.

    Args:
        name:      Tool name (must be a key in TOOL_IMPLS).
        arguments: Dict of keyword arguments for the tool.

    Returns:
        Dict with the tool's result or an error field.
    """
    if name not in TOOL_IMPLS:
        return {"error": f"Unknown tool: {name!r}. Available: {list(TOOL_IMPLS)}"}
    try:
        return TOOL_IMPLS[name](**arguments)
    except TypeError as exc:
        return {"error": f"Invalid arguments for tool {name!r}: {exc}"}
