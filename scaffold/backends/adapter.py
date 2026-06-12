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
        # oMLX may require OMLX_API_KEY; VibeProxy ignores the key.
        return OpenAI(base_url=b["base_url"], api_key=...), b["model"]

Embeddings are intentionally NOT handled here - they always go to oMLX
regardless of the generation backend (VibeProxy has no /v1/embeddings).
See memory/store.py for the embedding client.
"""

import os
import time
from typing import Any, Callable, TypeVar

from openai import (
    OpenAI,
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)

# Importing config triggers load_dotenv() so .env is populated into os.environ
# before any os.getenv() below runs. Without this, an entrypoint that imports
# adapter without first importing config (e.g. evals/behavior_test) silently
# falls back to the hardcoded defaults instead of reading .env.
import config as _config  # noqa: F401  (side-effect import: triggers load_dotenv)

_ = _config  # mark as intentionally used (side-effect-only import)

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
    # oMLX may require an API key (set OMLX_API_KEY in oMLX Preferences).
    # VibeProxy uses OAuth and ignores the key, so any placeholder works for it.
    api_key = (
        os.getenv("OMLX_API_KEY", "not-needed") if key == "omlx"
        else os.getenv("LLM_API_KEY", "not-needed")
    )
    # Per-request timeout so a hung local model (a large model on 16GB will
    # crawl) doesn't block forever. We do our OWN retry below, so disable the
    # SDK's built-in retries to keep the backoff policy in one visible place.
    timeout_s = float(os.getenv("LLM_TIMEOUT_S", "60"))
    client = OpenAI(
        base_url=b["base_url"], api_key=api_key,
        timeout=timeout_s, max_retries=0,
    )
    return client, b["model"]


# ---------------------------------------------------------------------------
# Retry policy (hand-rolled - no tenacity dep; the curriculum stays openai+numpy)
# ---------------------------------------------------------------------------
# The retryable-vs-fatal taxonomy: these backends are RATE-LIMITED (so 429s are
# EXPECTED), and a local model can hang (timeout). One transient blip must not
# end an unattended self-improvement cycle. 4xx-auth/bad-request are FATAL -
# retrying them just wastes the rate-limit budget.
_RETRYABLE = (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)
_T = TypeVar("_T")


def _with_retry(fn: Callable[[], _T], *, max_attempts: int = 4, base_delay: float = 1.0) -> _T:
    """Call fn(), retrying RETRYABLE errors with capped exponential backoff +
    jitter. Fatal errors (auth/bad-request) raise immediately - retrying them
    only burns rate-limit headroom."""
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except _RETRYABLE:
            if attempt == max_attempts:
                raise
            # capped exponential backoff; deterministic jitter (no random dep)
            delay = min(base_delay * (2 ** (attempt - 1)), 30.0)
            jitter = (attempt * 0.137) % 0.5
            time.sleep(delay + jitter)
            continue
    raise RuntimeError("unreachable")  # pragma: no cover


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
    response = _with_retry(lambda: client.chat.completions.create(
        model=model or default_model,
        messages=messages,  # type: ignore[arg-type]  # plain dicts are valid at runtime
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    ))
    return response.choices[0].message.content or ""


def tool_call(
    system: str,
    user: str,
    tool_name: str,
    input_schema: dict[str, Any],
    backend: str | None = None,
    model: str | None = None,
    max_tokens: int = 1024,
) -> dict[str, Any] | None:
    """
    Force a single, schema-validated tool call via the backend's native
    Anthropic Messages endpoint (/v1/messages) and return the tool input dict.

    Why this exists: a system-prompt instruction asking for JSON is not reliable
    on chatty cloud models (Claude via VibeProxy preambles in prose and invents
    keys - the curriculum's own "L1 prompt alone fails" finding). Anthropic
    tool use with a forced `tool_choice` compiles the schema server-side and
    GUARANTEES the requested fields. Both backends expose /v1/messages (oMLX
    Anthropic-compat on :8000, VibeProxy on :8317), so this is portable; it
    returns None if the endpoint is unavailable or returns no tool_use block,
    so callers can fall back to the OpenAI-compat path.

    Uses stdlib urllib (no new dependency).
    """
    import json as _json
    import urllib.request as _ur
    import urllib.error as _ue

    key = backend or os.getenv("AGENT_BACKEND", "omlx")
    if key not in BACKENDS:
        raise ValueError(f"Unknown backend {key!r}. Valid: {list(BACKENDS)}")
    b = BACKENDS[key]
    url = b["base_url"].rstrip("/") + "/messages"   # base_url ends in /v1
    api_key = (
        os.getenv("OMLX_API_KEY", "not-needed") if key == "omlx"
        else os.getenv("LLM_API_KEY", "not-needed")
    )
    payload = {
        "model": model or b["model"],
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "tools": [{"name": tool_name, "description": f"Produce a {tool_name} result.",
                   "input_schema": input_schema}],
        "tool_choice": {"type": "tool", "name": tool_name},
    }
    req = _ur.Request(
        url,
        data=_json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": api_key,                  # native Anthropic auth header
            "authorization": f"Bearer {api_key}",  # VibeProxy/oMLX tolerate either
        },
        method="POST",
    )
    timeout_s = float(os.getenv("LLM_TIMEOUT_S", "60"))
    try:
        with _ur.urlopen(req, timeout=timeout_s) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
    except (_ue.URLError, TimeoutError, ValueError):
        return None

    # Shape 1 - native Anthropic tool_use block (VibeProxy / real Anthropic).
    for block in data.get("content", []):
        if block.get("type") == "tool_use" and isinstance(block.get("input"), dict):
            return block["input"]

    # Shape 2 - text-faked tool call (oMLX local models render the call as TEXT,
    # e.g. <tools>{"name": ..., "arguments": {...}}</tools>, with no tool_use
    # block). Extract the first balanced {...} from any text block and unwrap an
    # "arguments"/"input" envelope if present.
    for block in data.get("content", []):
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            obj = _first_json_obj(block["text"])
            if isinstance(obj, dict):
                for envelope in ("arguments", "input", "parameters"):
                    if isinstance(obj.get(envelope), dict):
                        return obj[envelope]
                return obj
    return None


def _first_json_obj(text: str) -> dict[str, Any] | None:
    """Return the first balanced {...} JSON object found in text, or None."""
    import json as _json
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = _json.loads(text[start:i + 1])
                        if isinstance(obj, dict):
                            return obj
                    except _json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


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

    # Embeddings hit oMLX, which may require a key - reuse OMLX_API_KEY.
    embed_key = os.getenv("OMLX_API_KEY", os.getenv("LLM_API_KEY", "not-needed"))
    emb_client = OpenAI(base_url=embed_base_url, api_key=embed_key)
    response = emb_client.embeddings.create(model=embed_model, input=texts)
    return [item.embedding for item in response.data]
