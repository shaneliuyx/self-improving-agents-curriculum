"""
frameworks/deepagents_backend.py - one model object, both backends.

Mirrors backends/adapter.py::make_client, but returns a LangChain ChatOpenAI
model object (what deepagents wants) instead of a raw openai client.

Backends:
  AGENT_BACKEND=omlx      (default) -> oMLX :8000/v1
  AGENT_BACKEND=vibeproxy           -> VibeProxy :8317/v1

Install:  pip install -e ".[frameworks]"   # installs deepagents + langchain-openai
Run:      python -m frameworks.deepagents_backend

deepagents and langchain_openai are optional deps; this module imports cleanly
even when they are absent. The RuntimeError is raised only when make_model()
is actually called.
"""

from __future__ import annotations

import os

try:
    from langchain_openai import ChatOpenAI  # type: ignore
    _LANGCHAIN_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dep
    _LANGCHAIN_AVAILABLE = False
    ChatOpenAI = None  # type: ignore


def make_model():  # -> ChatOpenAI
    """
    Return a LangChain ChatOpenAI pointed at oMLX or VibeProxy depending on
    the AGENT_BACKEND env var.  Mirrors backends/adapter.py::make_client but
    returns a LangChain model object (what deepagents wants).

    Raises RuntimeError if langchain_openai is not installed.
    """
    if not _LANGCHAIN_AVAILABLE:  # pragma: no cover
        raise RuntimeError(
            "langchain_openai is not installed.\n"
            "Run:  pip install -e \".[frameworks]\"\n"
            "(this installs deepagents and langchain-openai)."
        )

    backend = os.getenv("AGENT_BACKEND", "omlx")
    if backend == "vibeproxy":
        # VibeProxy uses OAuth; the api_key is ignored but must be non-empty.
        return ChatOpenAI(
            base_url="http://localhost:8317/v1",
            api_key=os.getenv("LLM_API_KEY", "not-needed"),
            model=os.getenv("VIBE_MODEL", "claude-sonnet-4-6"),
            temperature=0.0,
        )
    # oMLX (default). Any model that supports tool-calling works.
    return ChatOpenAI(
        base_url="http://localhost:8000/v1",
        api_key=os.getenv("OMLX_API_KEY", "not-needed"),
        model=os.getenv("OMLX_MODEL", "Qwen2.5-Coder-7B-Instruct-MLX-4bit"),
        temperature=0.0,
    )


def _demo() -> None:
    print("deepagents_backend demo: model object for current AGENT_BACKEND\n")
    try:
        m = make_model()
        print(f"  model={m.model_name}  base_url={m.openai_api_base}")
    except RuntimeError as exc:
        print(exc)


if __name__ == "__main__":
    _demo()
