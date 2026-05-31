"""
frameworks/pydantic_ai_loop.py - Pydantic AI as a drop-in for agent/loop.py.

Pydantic AI (https://github.com/pydantic/pydantic-ai, 17k+ stars) is the
cleanest, least-opaque way to "graduate" the hand-built ReAct loop from
Module 03. It runs the tool-calling loop for you while staying explicit about
types and provider config - and it accepts a custom OpenAI-compatible base_url
in ONE line, so it targets oMLX / VibeProxy with no other changes.

Compare this file side-by-side with agent/loop.py: the loop, tool dispatch, and
message history you wrote by hand are what Pydantic AI's Agent.run_sync() does
internally. Build the raw version first (Module 03) so you know what is hidden.

Install:  pip install -e ".[frameworks]"          # installs pydantic-ai
Run:      python -m frameworks.pydantic_ai_loop    # needs a backend running
"""

from __future__ import annotations

import os

# Reuse the lab's backend registry so the base_url stays single-sourced.
from backends.adapter import BACKENDS


def build_agent():
    """
    Construct a Pydantic AI Agent pointed at the configured lab backend.

    The only backend-specific line is OpenAIProvider(base_url=...). Everything
    else (tools, system prompt, the ReAct loop) is framework-managed.
    """
    try:
        from pydantic_ai import Agent  # type: ignore
        from pydantic_ai.models.openai import OpenAIChatModel  # type: ignore
        from pydantic_ai.providers.openai import OpenAIProvider  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dep
        raise ImportError(
            "pydantic-ai is not installed. Run:  pip install -e \".[frameworks]\""
        ) from exc

    backend_name = os.getenv("AGENT_BACKEND", "omlx")
    backend = BACKENDS[backend_name]
    # oMLX may require a key (OMLX_API_KEY); VibeProxy uses OAuth and ignores it.
    api_key = (
        os.getenv("OMLX_API_KEY", "not-needed") if backend_name == "omlx"
        else os.getenv("LLM_API_KEY", "not-needed")
    )
    model = OpenAIChatModel(
        backend["model"],
        provider=OpenAIProvider(base_url=backend["base_url"], api_key=api_key),
    )
    agent = Agent(
        model,
        system_prompt=(
            "You are a precise assistant. Use the calculator tool for any "
            "arithmetic instead of computing it yourself."
        ),
    )

    # Same calculator capability as agent/tools.py, but registered the
    # Pydantic AI way - the framework handles schema + dispatch from the
    # function signature and docstring.
    @agent.tool_plain
    def calculator(expression: str) -> str:
        """Evaluate a basic arithmetic expression like '12 * (3 + 4)'."""
        allowed = set("0123456789+-*/(). ")
        if not set(expression) <= allowed:
            return "error: only numbers and + - * / ( ) are allowed"
        try:
            return str(eval(expression, {"__builtins__": {}}, {}))  # noqa: S307 - sandboxed chars
        except Exception as exc:  # noqa: BLE001
            return f"error: {exc}"

    return agent


def run(task: str) -> str:
    """Run one task through the framework-managed loop and return the answer."""
    agent = build_agent()
    result = agent.run_sync(task)
    return result.output


def _demo() -> None:
    print("Pydantic AI drop-in demo (needs oMLX :8000 or VibeProxy :8317 running)\n")
    try:
        answer = run("What is 17 * 23 + 5? Use the calculator tool.")
    except ImportError as exc:
        print(exc)
        return
    print("answer:", answer)


if __name__ == "__main__":
    _demo()
