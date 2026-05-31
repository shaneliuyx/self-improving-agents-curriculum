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
    # Resolve to an absolute path and verify it's inside the project root
    try:
        abs_path = (_PROJECT_ROOT / path).resolve()
        abs_root = _PROJECT_ROOT.resolve()
    except Exception as exc:
        return {"error": f"Path resolution failed: {exc}"}

    if not str(abs_path).startswith(str(abs_root)):
        return {"error": "Access denied: path is outside the project directory"}

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


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TOOL_IMPLS: dict[str, Any] = {
    "calculator": _tool_calculator,
    "read_file":  _tool_read_file,
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
