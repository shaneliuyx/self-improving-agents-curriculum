"""
memory/store.py - THIN SHIM over ``agentkit.memory``.

The hand-rolled SQLite vector store this file used to contain now lives in
agentkit (``agentkit.memory.store.MemoryStore`` / ``MemoryEntry``). The lab is a
CONSUMER of agentkit: it imports the library's implementation instead of
duplicating it. See agentkit's module map and ``docs/DESIGN.md``.

What this shim adds on top of the library (the lab-specific glue):

  * agentkit injects the ``Embedder`` (``MemoryStore(db_path, embedder=...)``).
    The lab's historical call-site is ``MemoryStore(db_path=...)`` with NO
    embedder, because in this lab embeddings ALWAYS go to the local oMLX
    ``/v1/embeddings`` endpoint regardless of the chat backend (VibeProxy has no
    embeddings route). So this shim supplies a default ``OMLXEmbedder`` bound to
    ``settings.embed_base_url`` / ``settings.embed_model`` when no embedder is
    passed, preserving the lab's zero-arg / ``db_path=`` ergonomics.

Everything else - schema, ``add``, ``search``, ``inject_context``, ``close``,
the ``<memory_context>`` injection format - is agentkit's, unchanged.
"""

from __future__ import annotations

from pathlib import Path

from openai import OpenAI

# The real implementation - imported from agentkit, not duplicated.
from agentkit.memory.store import MemoryEntry  # noqa: F401  (re-exported)
from agentkit.memory.store import MemoryStore as _AgentkitMemoryStore

from config import settings

__all__ = ["MemoryStore", "MemoryEntry", "OMLXEmbedder"]


class OMLXEmbedder:
    """The lab's default ``agentkit.types.Embedder`` - always local oMLX.

    agentkit only defines the ``Embedder`` Protocol (``embed(texts) -> vectors``);
    the concrete adapter lives operator-side, here. Embeddings never go to
    VibeProxy (it has no ``/v1/embeddings``), so this is hardwired to the oMLX
    embeddings endpoint from ``config.settings``.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.base_url = base_url or settings.embed_base_url
        self.model = model or settings.embed_model
        self._client = OpenAI(
            base_url=self.base_url,
            api_key=api_key or settings.omlx_api_key,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]


class MemoryStore(_AgentkitMemoryStore):
    """agentkit's ``MemoryStore`` with the lab's default local-oMLX embedder.

    Subclassed (not aliased) only to keep the lab's historical constructor
    signature - ``MemoryStore(db_path=...)`` with no required embedder. When an
    ``embedder`` is supplied it is used as-is (full agentkit DI); otherwise the
    default ``OMLXEmbedder`` is injected. All behavior - schema, add, search,
    inject_context, close - is inherited from agentkit.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        embedder: object | None = None,
    ) -> None:
        resolved_path = db_path if db_path is not None else settings.memory_db_path
        resolved_embedder = embedder if embedder is not None else OMLXEmbedder()
        super().__init__(resolved_path, embedder=resolved_embedder)


if __name__ == "__main__":
    # Smoke: the shim composes and re-exports agentkit's types (no network).
    print("memory.store shim -> agentkit.memory.store")
    print("  MemoryStore base:", _AgentkitMemoryStore.__module__)
    print("  MemoryEntry from:", MemoryEntry.__module__)
