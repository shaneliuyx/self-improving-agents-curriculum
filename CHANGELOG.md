# Changelog

All notable changes to the curriculum and scaffold. The `/improve-curriculum` command
appends a dated entry here each time it refreshes the material from new sources.

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
