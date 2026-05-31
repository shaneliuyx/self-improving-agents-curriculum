"""
frameworks/mem0_memory.py - mem0 as a drop-in for memory/store.py.

mem0 (https://github.com/mem0ai/mem0, 57k+ stars) is the most popular agent
memory layer. It does LLM-driven fact extraction, dedup, and vector retrieval -
the exact extract -> embed -> upsert pipeline that memory/store.py teaches by
hand in Module 04. This adapter shows how to point mem0 at OUR backends so the
generation + embedding both stay local / on-subscription, with no paid API.

KEY POINT (the whole reason this is in the curriculum): every LLM/embedder mem0
uses is configured with a custom OpenAI-compatible base_url, so mem0 runs
entirely on oMLX / VibeProxy. Generation can be either backend; embeddings are
always local (oMLX), exactly like the rest of the lab.

Install:  pip install -e ".[frameworks]"     # installs mem0ai
Run:      python -m frameworks.mem0_memory    # tiny demo (needs oMLX running)

This is a *reference* implementation. For learning the mechanism, build
memory/store.py first; reach for mem0 when you want dedup, scoping, and a
maintained vector pipeline for free.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

# Reuse the lab's single source of truth for backend base URLs.
from backends.adapter import BACKENDS


@dataclass
class Mem0Hit:
    """A retrieved memory, mirroring memory/store.MemoryEntry's shape."""
    content: str
    score: float
    metadata: dict[str, Any]


def _mem0_config() -> dict[str, Any]:
    """
    Build a mem0 config whose LLM + embedder both target the lab's local
    endpoints. Generation follows AGENT_BACKEND; embeddings are always oMLX.
    """
    gen = BACKENDS[os.getenv("AGENT_BACKEND", "omlx")]
    embed_base = os.getenv("EMBED_BASE_URL", "http://localhost:8000/v1")
    embed_model = os.getenv("EMBED_MODEL", "Qwen3-Embedding-0.6B-4bit-DWQ")
    omlx_key = os.getenv("OMLX_API_KEY", "not-needed")
    gen_key = omlx_key if os.getenv("AGENT_BACKEND", "omlx") == "omlx" else os.getenv("LLM_API_KEY", "not-needed")
    return {
        # LLM that mem0 uses to extract/condense facts from raw messages.
        "llm": {
            "provider": "openai",
            "config": {
                "model": gen["model"],
                "openai_base_url": gen["base_url"],
                "api_key": gen_key,
            },
        },
        # Embedder is ALWAYS the local oMLX endpoint (VibeProxy has none).
        "embedder": {
            "provider": "openai",
            "config": {
                "model": embed_model,
                "openai_base_url": embed_base,
                "api_key": omlx_key,
            },
        },
        # Local, file-backed vector store so the demo needs no extra service.
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": "sia_lab",
                "path": os.getenv("MEM0_CHROMA_PATH", "./.mem0_chroma"),
            },
        },
    }


class Mem0Store:
    """
    Drop-in-ish replacement for memory/store.MemoryStore, backed by mem0.

    Conceptual mapping:
        MemoryStore.add(type, content, meta)  ->  Mem0Store.add(content, meta)
        MemoryStore.search(query, ...)         ->  Mem0Store.search(query, ...)

    mem0 adds, for free: LLM fact-extraction, similarity dedup, and per-scope
    (user_id) namespacing - things memory/store.py leaves as exercises.
    """

    def __init__(self, scope: str = "agent") -> None:
        try:
            from mem0 import Memory  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dep
            raise ImportError(
                "mem0 is not installed. Run:  pip install -e \".[frameworks]\"\n"
                "(this installs the optional 'mem0ai' package)."
            ) from exc
        self.scope = scope
        self._mem = Memory.from_config(_mem0_config())

    def add(self, content: str, metadata: dict[str, Any] | None = None) -> None:
        """Store a memory. mem0 extracts the salient fact(s) via the LLM."""
        self._mem.add(content, user_id=self.scope, metadata=metadata or {})

    def search(self, query: str, top_k: int = 5) -> list[Mem0Hit]:
        """Retrieve the most relevant memories for a query."""
        # mem0 2.x: scope goes in filters=, and the arg is top_k (not limit).
        res = self._mem.search(query, filters={"user_id": self.scope}, top_k=top_k)  # type: ignore[call-arg]
        # mem0 returns {"results": [{"memory": str, "score": float, "metadata": {...}}, ...]}
        rows = res.get("results", res) if isinstance(res, dict) else res
        return [
            Mem0Hit(
                content=r.get("memory", ""),
                score=float(r.get("score", 0.0)),
                metadata=r.get("metadata", {}) or {},
            )
            for r in rows
        ]


def _demo() -> None:
    print("mem0 drop-in demo (requires oMLX running on :8000 for embeddings)\n")
    try:
        store = Mem0Store(scope="demo")
    except ImportError as exc:
        print(exc)
        return
    store.add("The user prefers small local models for cheap classification steps.")
    store.add("Reflection must be anchored to an external check to avoid recursive drift.")
    for hit in store.search("how should cheap steps be routed?", top_k=3):
        print(f"  [{hit.score:.3f}] {hit.content}")


if __name__ == "__main__":
    _demo()
