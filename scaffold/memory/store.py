"""
memory/store.py - SQLite-backed episodic/semantic/procedural memory store.

Three memory types (from the curriculum):
  episodic    - specific past events: (task, trajectory, outcome, timestamp)
  semantic    - general facts and heuristics extracted by reflection
  procedural  - reusable skills and how-to instructions

Retrieval is by cosine similarity over embeddings produced by the LOCAL oMLX
embeddings endpoint (EMBED_BASE_URL). This never calls VibeProxy because
VibeProxy has no /v1/embeddings endpoint.

Schema:
  memories(id, memory_type, content, embedding_blob, metadata_json, created_at)

Usage:
  store = MemoryStore()
  store.add("episodic", "Solved arithmetic task", {"task": "2+2", "answer": 4})
  results = store.search("arithmetic problem", top_k=3)
"""

from __future__ import annotations

import json
import sqlite3
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from openai import OpenAI

from config import settings


# ---------------------------------------------------------------------------
# Embedding helper (always local oMLX)
# ---------------------------------------------------------------------------

def _embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed texts using the local oMLX embeddings endpoint.

    Always uses EMBED_BASE_URL (defaults to http://localhost:8000/v1).
    Never routes to VibeProxy.
    """
    client = OpenAI(base_url=settings.embed_base_url, api_key=settings.omlx_api_key)
    response = client.embeddings.create(model=settings.embed_model, input=texts)
    return [item.embedding for item in response.data]


def _vec_to_blob(vec: list[float]) -> bytes:
    """Pack a float list into a compact binary blob for SQLite storage."""
    return struct.pack(f"{len(vec)}f", *vec)


def _blob_to_vec(blob: bytes) -> np.ndarray:
    """Unpack a binary blob back into a numpy array."""
    n = len(blob) // 4  # 4 bytes per float32
    return np.array(struct.unpack(f"{n}f", blob), dtype=np.float32)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors. Returns 0 if either is zero."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


# ---------------------------------------------------------------------------
# Memory entry dataclass
# ---------------------------------------------------------------------------

@dataclass
class MemoryEntry:
    """A single memory retrieved from the store."""
    id: int
    memory_type: str        # "episodic" | "semantic" | "procedural"
    content: str
    metadata: dict[str, Any]
    similarity: float       # cosine similarity to the query (0-1)
    created_at: float       # unix timestamp


# ---------------------------------------------------------------------------
# MemoryStore
# ---------------------------------------------------------------------------

class MemoryStore:
    """
    SQLite + numpy cosine-similarity vector store.

    All embeddings are computed locally via oMLX. The store is append-only
    by design (immutable data prevents hidden side-effects and makes the
    improvement history fully auditable).
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.memory_db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_type    TEXT    NOT NULL,
                content        TEXT    NOT NULL,
                embedding_blob BLOB,
                metadata_json  TEXT    NOT NULL DEFAULT '{}',
                created_at     REAL    NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_type ON memories(memory_type)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add(
        self,
        memory_type: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        embed: bool = True,
    ) -> int:
        """
        Add a new memory entry.

        Args:
            memory_type: "episodic" | "semantic" | "procedural"
            content:     The text content to store and embed.
            metadata:    Arbitrary JSON-serialisable metadata dict.
            embed:       Whether to compute and store an embedding.
                         Set False for bulk imports where you add embeddings later.

        Returns:
            The new row's integer id.
        """
        blob: bytes | None = None
        if embed:
            try:
                vectors = _embed_texts([content])
                blob = _vec_to_blob(vectors[0])
            except Exception as exc:
                # Embedding failures are non-fatal; store without a vector.
                # The entry will not appear in similarity search results.
                import warnings
                warnings.warn(
                    f"Embedding failed (will store without vector): {exc}",
                    stacklevel=2,
                )

        cursor = self._conn.execute(
            """
            INSERT INTO memories (memory_type, content, embedding_blob, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                memory_type,
                content,
                blob,
                json.dumps(metadata or {}),
                time.time(),
            ),
        )
        self._conn.commit()
        # lastrowid is Optional in the type stubs but always set after an INSERT.
        return cursor.lastrowid if cursor.lastrowid is not None else -1

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        memory_type: str | None = None,
        top_k: int = 5,
    ) -> list[MemoryEntry]:
        """
        Retrieve the top_k most similar memories for a query string.

        Args:
            query:       The search query (will be embedded locally).
            memory_type: Optional filter ("episodic", "semantic", "procedural").
            top_k:       Number of results to return.

        Returns:
            List of MemoryEntry sorted by descending cosine similarity.
        """
        try:
            query_vec = np.array(_embed_texts([query])[0], dtype=np.float32)
        except Exception as exc:
            raise RuntimeError(f"Failed to embed query: {exc}") from exc

        # Fetch all rows that have embeddings
        if memory_type:
            rows = self._conn.execute(
                "SELECT id, memory_type, content, embedding_blob, metadata_json, created_at "
                "FROM memories WHERE memory_type=? AND embedding_blob IS NOT NULL",
                (memory_type,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, memory_type, content, embedding_blob, metadata_json, created_at "
                "FROM memories WHERE embedding_blob IS NOT NULL"
            ).fetchall()

        scored: list[tuple[float, MemoryEntry]] = []
        for row_id, rtype, content, blob, meta_json, created_at in rows:
            vec = _blob_to_vec(blob)
            sim = _cosine_similarity(query_vec, vec)
            entry = MemoryEntry(
                id=row_id,
                memory_type=rtype,
                content=content,
                metadata=json.loads(meta_json),
                similarity=sim,
                created_at=created_at,
            )
            scored.append((sim, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    def inject_context(self, query: str, k: int = 4) -> str:
        """
        Retrieve the top-k memories relevant to `query` and format them as a
        compact `<memory_context>` block for injection into the agent's system
        prompt BEFORE it acts. This is the read side of the experience layer:
        without it, reflection writes lessons that the loop never reads back,
        so the agent restarts blind on every task (the write-only gap).

        Returns "" (empty string) when there is nothing useful to inject -
        no memories yet, or embeddings unavailable - so the caller can safely
        concatenate the result unconditionally. Never raises: a memory miss
        must not break the ACT loop.
        """
        try:
            hits = self.search(query, top_k=k)
        except Exception:
            # Embedding endpoint down / no embeddings: degrade to no context,
            # never break the loop. The agent simply runs without prior lessons.
            return ""
        # Only inject reasonably-relevant hits; a 0.0-similarity row is noise.
        useful = [h for h in hits if h.similarity > 0.0]
        if not useful:
            return ""
        lines = [
            f"- ({h.memory_type}, sim={h.similarity:.2f}) {h.content}"
            for h in useful
        ]
        return (
            "<memory_context>\n"
            "Relevant lessons from your past experience (use them; do not repeat past mistakes):\n"
            + "\n".join(lines)
            + "\n</memory_context>"
        )

    def record_trajectory(self, trajectory: dict, salience: float = 0.5) -> int:
        """
        Convenience wrapper: store one agent trajectory as an episodic memory.
        `salience` (0-1) is kept in metadata for later recency/salience ranking.
        Thin sugar over add() so callers (scripts/go, the loop) have a single
        verb for the RECORD step that note 04 documents.
        """
        content = trajectory.get("summary") or json.dumps(trajectory)[:2000]
        return self.add(
            "episodic",
            content,
            metadata={"salience": float(salience), **trajectory.get("metadata", {})},
        )

    def get_recent(
        self,
        memory_type: str | None = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Return the most recent memories (by insertion time), optionally filtered by type."""
        if memory_type:
            rows = self._conn.execute(
                "SELECT id, memory_type, content, embedding_blob, metadata_json, created_at "
                "FROM memories WHERE memory_type=? ORDER BY created_at DESC LIMIT ?",
                (memory_type, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, memory_type, content, embedding_blob, metadata_json, created_at "
                "FROM memories ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

        return [
            MemoryEntry(
                id=r[0], memory_type=r[1], content=r[2],
                metadata=json.loads(r[4]), similarity=0.0, created_at=r[5],
            )
            for r in rows
        ]

    def count(self, memory_type: str | None = None) -> int:
        """Return the total number of stored memories."""
        if memory_type:
            return self._conn.execute(
                "SELECT COUNT(*) FROM memories WHERE memory_type=?", (memory_type,)
            ).fetchone()[0]
        return self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
