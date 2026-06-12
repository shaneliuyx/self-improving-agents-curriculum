"""
tests/test_buggy.py - intentionally failing test for the deepagents codefix agent.

The codefix agent's task (frameworks/deepagents_codefix.py) is:
  read this test -> find the source bug -> make the smallest edit -> re-run.

The bug: src/buggy_math.py::add() subtracts instead of adds.
The fix: change `return a - b` to `return a + b` in src/buggy_math.py.

Keep this file tiny and self-contained so the agent has a single clear target.
Do NOT edit this test file - the agent must fix the source, not the test.
"""

import sys
import os

# Allow import from src/ without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from buggy_math import add  # type: ignore
except ImportError:
    # If src/buggy_math.py doesn't exist yet, fail with a clear message.
    import pytest
    pytest.skip("src/buggy_math.py not found - create it for the codefix lab", allow_module_level=True)


def test_add_positive():
    assert add(2, 3) == 5, "add(2, 3) should return 5"


def test_add_zero():
    assert add(0, 0) == 0, "add(0, 0) should return 0"


def test_add_negative():
    assert add(-1, -1) == -2, "add(-1, -1) should return -2"
