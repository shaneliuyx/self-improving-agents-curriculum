# Self-Improving Agent Lab

A **learning scaffold** for building self-improving agents on Apple Silicon,
running entirely local (oMLX) or via a Claude subscription proxy (VibeProxy).
No paid API calls. No cloud required.

> **Human-in-the-loop notice** — this is an educational scaffold, not
> production software. Keep a human reviewing every improvement the agent
> proposes. Run `scripts/commit` after each iteration so every change is
> revertible via `git revert`. Never let the loop run unattended against
> important files.

---

## Prerequisites

You need ONE of:

| Backend | What it is | URL |
|---------|-----------|-----|
| **oMLX** | Native macOS menu-bar MLX inference server | `http://localhost:8000/v1` |
| **VibeProxy** | Routes your Claude MAX subscription through a local proxy | `http://localhost:8317/v1` |

- Python 3.11+
- git (for `scripts/commit`)
- oMLX running with an embedding model (e.g. `nomic-embed-text`) — required
  even when generating via VibeProxy, because VibeProxy has no embeddings
  endpoint.

---

## Setup

```bash
git clone <this-repo> self-improving-agent-lab
cd self-improving-agent-lab
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set AGENT_BACKEND=omlx or vibeproxy, and OMLX_MODEL / VIBE_MODEL
```

---

## Configuration (.env)

```
AGENT_BACKEND=omlx          # or vibeproxy
OMLX_MODEL=qwen2.5-coder-7b
VIBE_MODEL=claude-sonnet-4-5
EMBED_BASE_URL=http://localhost:8000/v1
EMBED_MODEL=nomic-embed-text
LLM_API_KEY=not-needed
```

The `EMBED_BASE_URL` always points at oMLX, regardless of generation backend.

---

## Run one improvement iteration

```bash
chmod +x scripts/go scripts/commit
./scripts/go
```

`scripts/go` will:
1. Print `GOAL.md` and `AGENTS.md` as context
2. Run a sample eval task through the agent
3. Reflect on the trajectory and extract lessons
4. Propose a skill or system-prompt improvement
5. Run verification gates
6. Keep or discard the proposal
7. Append to `CHANGELOG.md`

---

## Layout

```
self-improving-agent-lab/
├── GOAL.md                 # One-sentence motto (agent-seed pattern)
├── AGENTS.md               # Operating contract the agent reads at start
├── CHANGELOG.md            # Improvement history (loop appends here)
├── config.py               # Loads .env, exposes settings
├── requirements.txt
├── .env.example
│
├── backends/
│   ├── adapter.py          # Unified OpenAI-SDK client for omlx / vibeproxy
│   └── router.py           # Route step difficulty -> backend/model
│
├── agent/
│   ├── tools.py            # Tool registry: calculator, read_file
│   └── loop.py             # ReAct ACT->observe loop; returns trajectory
│
├── memory/
│   └── store.py            # SQLite + numpy cosine-similarity vector store
│
├── reflection/
│   └── reflect.py          # LLM-based trajectory critique -> lessons
│
├── skills/
│   ├── library.py          # Propose, validate, save, load skills
│   └── SKILLS/             # Saved skill files (markdown + json)
│
├── verification/
│   └── gates.py            # Verification gates: accept / reject / escalate
│
├── evolve/
│   ├── loop.py             # DGM-style system-prompt evolution
│   └── archive/            # Versioned system-prompt variants
│
├── evals/
│   ├── tasks.py            # Small deterministic task set
│   └── run.py              # Run agent over tasks; compare variants
│
└── scripts/
    ├── go                  # Main entrypoint (bash)
    └── commit              # Safe git commit wrapper (bash)
```

---

## Architecture overview

```
GOAL.md / AGENTS.md
      │
      ▼
  scripts/go  ──►  agent/loop.py  (ReAct, tools)
                        │
                   memory/store.py  ◄── embed via oMLX (always local)
                        │
                   reflection/reflect.py
                        │
                   skills/library.py  OR  evolve/loop.py
                        │
                   verification/gates.py  (gate every change)
                        │
                   scripts/commit  (every accepted change is committed)
```

---

## Learning path

This scaffold corresponds to the "Building Self-Improving Agents" curriculum:

- Module 03: `agent/loop.py` - the minimal ReAct loop
- Module 04: `memory/store.py` - episodic/semantic/procedural memory
- Module 05: `reflection/reflect.py` - structured reflection
- Module 06: `skills/library.py` - skill acquisition
- Module 07: `verification/gates.py` - verification gates
- Module 08: `evolve/loop.py` - DGM-style self-modification

---

## Cautions

- VibeProxy routes your Claude subscription through a local proxy. This may
  violate Anthropic's Terms of Service. Use it only for personal experimentation.
- These backends are rate-limited, not per-token-metered. Many-call loops are
  effectively free in dollar terms but bounded by local throughput.
- Never remove the verification gate (`verification/gates.py`). It is the
  spine that prevents "recursive drift" - an agent that improves itself into
  uselessness.
