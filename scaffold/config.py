"""
config.py - Central settings loader.

Reads .env (if present) and exposes a single `settings` object used by all
modules. Import this instead of calling os.getenv() directly so there is one
authoritative place for defaults and validation.
"""

import os
from pathlib import Path

# Load .env if python-dotenv is available (non-fatal if missing)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # python-dotenv is optional; env vars may be set by the shell


class Settings:
    """Immutable-ish settings bag populated from environment variables."""

    # ---------------------------------------------------------------------------
    # Generation backend
    # ---------------------------------------------------------------------------
    backend: str = os.getenv("AGENT_BACKEND", "omlx")
    """omlx | vibeproxy - selects which local proxy handles chat completions."""

    omlx_model: str = os.getenv("OMLX_MODEL", "qwen2.5-coder-7b")
    vibe_model: str = os.getenv("VIBE_MODEL", "claude-sonnet-4-5-20250929")
    llm_api_key: str = os.getenv("LLM_API_KEY", "not-needed")
    # oMLX API key (oMLX Preferences -> API). Used for oMLX chat AND embeddings.
    # Falls back to LLM_API_KEY / "not-needed" when oMLX auth is disabled.
    omlx_api_key: str = os.getenv("OMLX_API_KEY", os.getenv("LLM_API_KEY", "not-needed"))

    # oMLX base URLs (chat AND embeddings live here)
    omlx_base_url: str = "http://localhost:8000/v1"
    # VibeProxy base URL (chat only - no embeddings endpoint)
    vibeproxy_base_url: str = "http://localhost:8317/v1"

    # ---------------------------------------------------------------------------
    # Embeddings - ALWAYS local oMLX, regardless of generation backend.
    # VibeProxy has no /v1/embeddings endpoint (Claude subscription only covers
    # chat). Centralising this here ensures no module accidentally routes
    # embeddings to VibeProxy.
    # ---------------------------------------------------------------------------
    embed_base_url: str = os.getenv("EMBED_BASE_URL", "http://localhost:8000/v1")
    embed_model: str = os.getenv("EMBED_MODEL", "Qwen3-Embedding-0.6B-4bit-DWQ")

    # ---------------------------------------------------------------------------
    # Agent loop behaviour
    # ---------------------------------------------------------------------------
    agent_max_rounds: int = int(os.getenv("AGENT_MAX_ROUNDS", "10"))
    """Maximum ReAct tool-call rounds before giving up on a task."""

    # ---------------------------------------------------------------------------
    # Evolution / verification
    # ---------------------------------------------------------------------------
    evolve_min_delta: float = float(os.getenv("EVOLVE_MIN_DELTA", "0.05"))
    """Minimum improvement in eval score (0-1) required to accept a mutation."""

    # ---------------------------------------------------------------------------
    # Filesystem paths (relative to the project root)
    # ---------------------------------------------------------------------------
    project_root: Path = Path(__file__).parent
    skills_dir: Path = project_root / "skills" / "SKILLS"
    evolve_archive_dir: Path = project_root / "evolve" / "archive"
    memory_db_path: Path = project_root / "memory" / "episodic.db"

    def active_model(self) -> str:
        """Return the model name for the currently configured backend."""
        if self.backend == "vibeproxy":
            return self.vibe_model
        return self.omlx_model

    def validate(self) -> None:
        """Raise ValueError for obviously wrong config combinations."""
        valid_backends = {"omlx", "vibeproxy"}
        if self.backend not in valid_backends:
            raise ValueError(
                f"AGENT_BACKEND={self.backend!r} is not valid. "
                f"Choose one of: {valid_backends}"
            )
        # Ensure required directories exist
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.evolve_archive_dir.mkdir(parents=True, exist_ok=True)
        self.memory_db_path.parent.mkdir(parents=True, exist_ok=True)


# Module-level singleton - import `settings` everywhere
settings = Settings()
