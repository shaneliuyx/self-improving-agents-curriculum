# Changelog

All notable changes to the curriculum and scaffold. The `/improve-curriculum` command
appends a dated entry here each time it refreshes the material from new sources.

## 2026-05-31 — Claude Agent SDK adapter + CI

- **Third framework adapter** `scaffold/frameworks/claude_agent_sdk_loop.py` — the Claude-native
  track ([Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python), what SIA + Nerve
  use). It bundles the Claude Code CLI and runs on your Claude **subscription** directly (no API key,
  no VibeProxy); intentionally ignores `base_url` since it does not fit the oMLX-local track. Added to
  the `[frameworks]` extra. Note 13 §5 corrected to reflect the subscription auth model.
- **GitHub Actions CI** (`.github/workflows/ci.yml`) — three jobs keep the repo green on every push/PR:
  scaffold `py_compile`, a Mermaid render-lint over every note (fails on invalid diagrams), and a
  wikilink resolver. All three verified green locally. Added a CI badge to the README.

## 2026-05-31 — Framework track + local-model prep

- **New module `13 - Graduating to a Framework`** — grounded in a verified investigation of the
  cited 2026 self-improving-agent projects (all real; none use LangChain/CrewAI/AutoGen — they run
  on raw SDKs, the Claude Agent SDK, or custom harnesses). Covers the make-or-break `base_url` test
  and a framework landscape table. Wired into the MOC roadmap, capstone, nav, and Canvas (14 nodes).
- **Optional framework adapters** in `scaffold/frameworks/`: `mem0_memory.py` (memory drop-in) and
  `pydantic_ai_loop.py` (loop drop-in), both backend-aware (oMLX/VibeProxy via custom `base_url`),
  with guarded optional imports. Added `[frameworks]` extra to `pyproject.toml`.
- **Module 02 preparation section** — which local models to install on 16–32 GB Macs (concrete
  `mlx-community` model IDs, RAM budgeting, and the "everyone installs the embedding model" rule).

## 2026-05-31 — Initial release

### Curriculum
- 13 modules (`00`–`12`) covering the full ACT → RECORD → REFLECT → LEARN → VERIFY loop,
  targeting local oMLX and Claude-MAX-via-VibeProxy backends.
- Obsidian Canvas map linking all modules.
- 27 Mermaid diagrams, audited: fixed literal `\n` line-breaks (→ `<br/>`), added consistent
  font/spacing init directives, and restructured over-wide diagrams to balanced layouts.

### Scaffold (`scaffold/`)
- Runnable Python lab: unified backend adapter, model router, ReAct agent loop, sqlite memory
  store (local embeddings), reflection, skill library, verification gate, DGM-style keep/discard
  evolve loop, eval harness, `scripts/go` iteration protocol, `scripts/commit` safe wrapper.
- `pyproject.toml` + `pyrightconfig.json` for clean imports / type-checking.

### Tooling (`tools/`, `.claude/commands/`)
- `/improve-curriculum` slash command (GATHER → REFLECT → LEARN → VERIFY → SHIP).
- `refresh-research.sh` (reproducible last30days research pull).
- `improve-workflow.js` (parallel, audited note updates).
- `curriculum-spec.md` (authoring contract).

### Meta
- `install.sh` for one-command setup on a new machine.
- Research provenance captured in `research/`.
