# Changelog

All notable changes to the curriculum and scaffold. The `/improve-curriculum` command
appends a dated entry here each time it refreshes the material from new sources.

## 2026-05-31 — oMLX API-key support + live end-to-end verification

- **Fixed: oMLX requires an API key.** The baked-in "local servers ignore the key" assumption was
  wrong — auth-enabled oMLX rejects requests. Added `OMLX_API_KEY` (used for oMLX **chat and
  embeddings**) across `adapter.py`, `config.py`, `memory/store.py`, `frameworks/mem0_memory.py`,
  `.env.example`, the spec, and notes 00/02. The Claude/VibeProxy track needs it too, since embeddings
  are always local.
- **Verified live** against a running oMLX (auth on): `adapter.chat`, `adapter.embed` (768-dim), and the
  full `MemoryStore` add + similarity search (correct ranking) all pass with
  `Qwen2.5-Coder-7B-Instruct-4bit` + `nomicai-modernbert-embed-base-bf16`. Both backends now proven
  end-to-end through the scaffold.

## 2026-05-31 — Verified model IDs against live backends

- **Fixed wrong model IDs** found by checking the HuggingFace API and a running VibeProxy:
  - VibeProxy serves dated IDs — the bare `claude-sonnet-4-5` is not valid. Updated the default to
    `claude-sonnet-4-5-20250929` across `adapter.py`, `config.py`, `router.py`, `.env.example`, the
    spec, and every note snippet (13 occurrences). Added a "run `curl :8317/v1/models`" tip to note 02.
  - The recommended embedding IDs did not exist (`mlx-community/nomic-embed-text-v1.5` → 401). Replaced
    with verified MLX embedders (`Qwen3-Embedding-0.6B-4bit-DWQ`, `bge-small-en-v1.5-bf16`,
    `nomicai-modernbert-embed-base-bf16`) in note 02 and the scaffold defaults.
  - Corrected an over-large model example (`qwen2.5-72b` → `Qwen2.5-Coder-14B-Instruct-4bit`).
- **Verified**: a real chat completion through VibeProxy (`localhost:8317`) and the lab's own
  `backends/adapter.py` (OpenAI SDK → VibeProxy) both return successfully.

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
