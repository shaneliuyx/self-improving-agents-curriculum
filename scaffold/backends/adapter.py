"""
backends/adapter.py - Unified OpenAI-SDK client for oMLX and VibeProxy.

Both backends expose an OpenAI-compatible /v1/chat/completions endpoint, so the
same openai.OpenAI client works for both. The only difference is base_url and
the model name string.

Canonical snippet (from the curriculum spec):

    BACKENDS = {
        "omlx":      {"base_url": "http://localhost:8000/v1", "model": ...},
        "vibeproxy": {"base_url": "http://localhost:8317/v1", "model": ...},
    }
    def make_client(backend=None):
        b = BACKENDS[backend or os.getenv("AGENT_BACKEND", "omlx")]
        return OpenAI(base_url=b["base_url"], api_key=os.getenv("LLM_API_KEY", "not-needed")), b["model"]

Embeddings are intentionally NOT handled here - they always go to oMLX
regardless of the generation backend (VibeProxy has no /v1/embeddings).
See memory/store.py for the embedding client.
"""

import os
from typing import Any

from openai import OpenAI

# ---------------------------------------------------------------------------
# Backend registry
# ---------------------------------------------------------------------------
BACKENDS: dict[str, dict[str, str]] = {
    "omlx": {
        "base_url": "http://localhost:8000/v1",
        "model": os.getenv("OMLX_MODEL", "qwen2.5-coder-7b"),
    },
    "vibeproxy": {
        # VibeProxy routes your Claude MAX subscription (OAuth, no API key needed).
        # Note: using a subscription via proxy may violate provider ToS.
        "base_url": "http://localhost:8317/v1",
        "model": os.getenv("VIBE_MODEL", "claude-sonnet-4-5-20250929"),  # run `curl localhost:8317/v1/models` for valid IDs
    },
}


def make_client(backend: str | None = None) -> tuple[OpenAI, str]:
    """
    Return (OpenAI client, model_name) for the given backend.

    Args:
        backend: "omlx" | "vibeproxy" | None.
                 None reads AGENT_BACKEND env var, defaulting to "omlx".

    Returns:
        (client, model) tuple ready for chat.completions.create(model=model, ...)
    """
    key = backend or os.getenv("AGENT_BACKEND", "omlx")
    if key not in BACKENDS:
        raise ValueError(
            f"Unknown backend {key!r}. Valid choices: {list(BACKENDS)}"
        )
    b = BACKENDS[key]
    # Local servers ignore the api_key field entirely.
    # VibeProxy uses OAuth under the hood, so any non-empty placeholder works.
    client = OpenAI(
        base_url=b["base_url"],
        api_key=os.getenv("LLM_API_KEY", "not-needed"),
    )
    return client, b["model"]


def chat(
    messages: list[dict[str, str]],
    backend: str | None = None,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    **kwargs: Any,
) -> str:
    """
    Thin helper: send messages to the configured backend, return the reply text.

    Args:
        messages:    OpenAI-format message list.
        backend:     Override backend (uses AGENT_BACKEND env var if None).
        model:       Override model name (uses backend default if None).
        temperature: Sampling temperature.
        max_tokens:  Maximum tokens in the reply.
        **kwargs:    Forwarded to chat.completions.create().

    Returns:
        The assistant's reply as a plain string.
    """
    client, default_model = make_client(backend)
    response = client.chat.completions.create(
        model=model or default_model,
        messages=messages,  # type: ignore[arg-type]  # plain dicts are valid at runtime
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )
    return response.choices[0].message.content or ""


def embed(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of strings using the LOCAL oMLX embeddings endpoint.

    This function ALWAYS uses oMLX (EMBED_BASE_URL), regardless of the
    generation backend. VibeProxy has no /v1/embeddings endpoint.

    Args:
        texts: List of strings to embed.

    Returns:
        List of embedding vectors (list of floats).
    """
    embed_base_url = os.getenv("EMBED_BASE_URL", "http://localhost:8000/v1")
    embed_model = os.getenv("EMBED_MODEL", "Qwen3-Embedding-0.6B-4bit-DWQ")

    emb_client = OpenAI(base_url=embed_base_url, api_key="not-needed")
    response = emb_client.embeddings.create(model=embed_model, input=texts)
    return [item.embedding for item in response.data]
