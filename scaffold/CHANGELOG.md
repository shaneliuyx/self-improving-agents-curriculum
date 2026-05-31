# Changelog

All accepted improvements are appended here by scripts/go.

## [0.1.0] - 2026-05-31

### Added
- Initial scaffold: backends, agent loop, memory store, reflection,
  skills library, verification gates, evolve loop, evals harness.
- GOAL.md, AGENTS.md operating contract (agent-seed pattern).
- scripts/go entrypoint and scripts/commit safe wrapper.

### Architecture
- Generation backend is swappable (oMLX / VibeProxy) via AGENT_BACKEND env var.
- Embeddings always route to local oMLX (EMBED_BASE_URL), never VibeProxy,
  because VibeProxy has no embeddings endpoint.
- Verification gate is mandatory before every LEARN step.
