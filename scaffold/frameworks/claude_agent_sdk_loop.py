"""
frameworks/claude_agent_sdk_loop.py - the Claude Agent SDK as the agent loop.

This is the most Claude-native "graduation" path and the one the two highest-signal
self-improving-agent projects actually use - SIA (567 stars) and Nerve (54 stars).
The Claude Agent SDK (https://github.com/anthropics/claude-agent-sdk-python) bundles
the Claude Code CLI and authenticates through your Claude subscription directly:
no API key, and - unlike the other adapters - NO VibeProxy needed. The SDK *is*
Claude Code, so it uses the same subscription auth Claude Code does.

TRACK FIT:
  - Claude / subscription track:  yes - this is its home.
  - oMLX local track:             NO. The SDK speaks the Anthropic/Claude Code
                                  shape, not an OpenAI-compatible local endpoint.
                                  Local-first users stay on agent/loop.py or
                                  frameworks/pydantic_ai_loop.py.

So this adapter intentionally ignores AGENT_BACKEND/base_url: it always runs
through your Claude subscription. It is included to show the Claude-native option
end to end, mirroring agent/loop.py's calculator capability.

Install:  pip install -e ".[frameworks]"             # adds claude-agent-sdk
Run:      python -m frameworks.claude_agent_sdk_loop  # uses your Claude subscription
"""

from __future__ import annotations


def _build_options(server):
    """Build ClaudeAgentOptions wiring our in-process calculator tool."""
    from claude_agent_sdk import ClaudeAgentOptions  # type: ignore

    return ClaudeAgentOptions(
        system_prompt=(
            "You are a precise assistant. Use the calculate tool for any "
            "arithmetic instead of computing it yourself."
        ),
        max_turns=3,
        mcp_servers={"lab": server},
        allowed_tools=["mcp__lab__calculate"],
    )


async def run(task: str) -> str:
    """
    Run one task through the Claude Agent SDK loop and return the assistant text.

    The SDK manages the ReAct loop, tool dispatch, and message history - the same
    machinery agent/loop.py builds by hand. Auth flows through your Claude
    subscription via the bundled Claude Code CLI.
    """
    try:
        from claude_agent_sdk import (  # type: ignore
            AssistantMessage,
            TextBlock,
            create_sdk_mcp_server,
            query,
            tool,
        )
    except ImportError as exc:  # pragma: no cover - optional dep
        raise ImportError(
            "claude-agent-sdk is not installed. Run:  pip install -e \".[frameworks]\"\n"
            "It also requires an active Claude subscription (the bundled Claude Code CLI uses it)."
        ) from exc

    # Same calculator capability as agent/tools.py, registered as an in-process
    # MCP tool. The SDK derives the schema from the {"expression": str} spec.
    @tool("calculate", "Evaluate a basic arithmetic expression", {"expression": str})
    async def calculate(args):
        expr = str(args.get("expression", ""))
        allowed = set("0123456789+-*/(). ")
        if not set(expr) <= allowed:
            text = "error: only numbers and + - * / ( ) are allowed"
        else:
            try:
                text = str(eval(expr, {"__builtins__": {}}, {}))  # noqa: S307 - sandboxed chars
            except Exception as exc:  # noqa: BLE001
                text = f"error: {exc}"
        return {"content": [{"type": "text", "text": text}]}

    server = create_sdk_mcp_server(name="lab-tools", version="1.0.0", tools=[calculate])
    options = _build_options(server)

    out: list[str] = []
    async for message in query(prompt=task, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    out.append(block.text)
    return "\n".join(out).strip()


def _demo() -> None:
    print("Claude Agent SDK demo (uses your Claude subscription via bundled Claude Code)\n")
    try:
        import anyio  # type: ignore
    except ImportError:
        print("Install deps first:  pip install -e \".[frameworks]\"")
        return
    try:
        answer = anyio.run(run, "What is 17 * 23 + 5? Use the calculate tool.")
    except ImportError as exc:
        print(exc)
        return
    print("answer:", answer)


if __name__ == "__main__":
    _demo()
