# Building Self-Improving Agents — Curriculum + Runnable Lab

[![ci](https://github.com/shaneliuyx/self-improving-agents-curriculum/actions/workflows/ci.yml/badge.svg)](https://github.com/shaneliuyx/self-improving-agents-curriculum/actions/workflows/ci.yml)

A hands-on, 15-module curriculum for building **self-improving AI agents** that run on
backends you already have — a **local model via [oMLX](https://omlx.ai)** (Apple Silicon)
or your **Claude MAX subscription via [VibeProxy](https://github.com/automazeio/vibeproxy)** —
with **no direct paid API calls**. It ships with a runnable Python scaffold and a slash
command that keeps the curriculum current by mining the last 30 days of research.

> Built from real May-2026 signal (Hacker News, GitHub, Reddit, arXiv). See [`research/`](research/)
> for the source material every claim is grounded in.

---

## Why this exists

Most "self-improving agent" material assumes a metered API key. This curriculum targets the
two backends a hobbyist/practitioner actually has on a Mac, where calls are **rate-limited, not
per-token-billed** — which changes the design: the many-call loops (reflect, critique,
keep/discard) that are expensive on an API are essentially free here.

```mermaid
%%{init: {"theme":"neutral","themeVariables":{"fontSize":"16px"},"flowchart":{"htmlLabels":true,"useMaxWidth":true}}}%%
flowchart TD
    App["Your agent"] --> Adapter["backends/adapter.py<br/>one OpenAI-compatible client"]
    Adapter -->|AGENT_BACKEND=omlx| oMLX["oMLX :8000<br/>local, chat + embeddings"]
    Adapter -->|AGENT_BACKEND=vibeproxy| VP["VibeProxy :8317<br/>Claude MAX, chat only"]
    App -->|embeddings always local| oMLX
```

The one rule the whole curriculum is built on: **generation backend is swappable; embeddings
are always local** (VibeProxy has no embeddings endpoint).

---

## What makes this different

There are good free courses for *building* an agent (Microsoft's
[ai-agents-for-beginners](https://github.com/microsoft/ai-agents-for-beginners), several
solid from-scratch repos). What this curriculum does that they don't:

- **Self-improvement is the whole spine, not a footnote.** Every module serves one loop -
  ACT → RECORD → REFLECT → LEARN, gated by VERIFY - across the three camps (code/weight
  self-modification, memory+skill accumulation, and the skeptic's "you probably want an
  automation"). You build the DGM-style keep/discard evolve loop and a label-free
  retrospective-optimization (RHO) loop yourself, not read about them.
- **Local-first *and* subscription-first, with no paid API.** One adapter targets a local
  model (oMLX) or your Claude subscription (via VibeProxy) by swapping a single env var.
  Most "from scratch" courses assume a metered OpenAI/Azure key; the local-only ones stop
  at memory/ReAct.
- **Rate-limited economics, not per-token.** Because these backends are rate-limited rather
  than billed per token, the many-call loops (reflection, critique, keep/discard, N-sample
  self-preference voting) that are expensive on a metered API are essentially free here -
  which changes what designs are practical.
- **VERIFY-gate-as-thesis.** Recursive drift (an agent that "improves" itself into confident
  nonsense) is the failure mode the whole curriculum is built to prevent - external
  evaluation gates every LEARN step, end to end.
- **A curriculum that refreshes itself.** The `/improve-curriculum` command mines the last
  30 days of research (arXiv, GitHub, HN) and updates the notes + scaffold, so citations
  don't rot. (This repo is itself maintained that way.)

---

## Repository layout

| Path | What |
|---|---|
| [`curriculum/`](curriculum/) | The 15 Obsidian notes (`00`–`14`) + a Canvas map. Rich Mermaid diagrams. Best viewed in [Obsidian](https://obsidian.md). |
| [`scaffold/`](scaffold/) | The runnable Python lab: agent loop, memory, reflection, skills, verification gate, DGM-style evolve loop, eval harness. |
| [`tools/`](tools/) | The maintenance automation: `refresh-research.sh`, `improve-workflow.js`, and the authoring spec. |
| [`.claude/commands/`](.claude/commands/) | The `/improve-curriculum` slash command. |
| [`research/`](research/) | Source research the curriculum is grounded in (provenance). |

### Curriculum modules

| # | Module | Focus |
|---|--------|-------|
| 00 | Curriculum Map | Hub, roadmap, the three camps |
| 01 | What Self-Improving Means | Taxonomy + the skeptic's "when NOT to build one" |
| 02 | Backends — oMLX & VibeProxy | Setup, unified adapter, embeddings-stay-local |
| 03 | The Minimal Agent Loop | ReAct baseline (you can't measure improvement without one) |
| 04 | Memory Systems | Episodic / semantic / procedural experience layer |
| 05 | Reflection & Self-Correction | The REFLECT step + the recursive-drift warning |
| 06 | Skill Acquisition & Curation | agent-seed pattern, SkillOS / Muse-Autoskill |
| 07 | Verification Gates & Layered Control | The L0–L3 hierarchy; "prompt alone failed" |
| 08 | Self-Modification — DGM Pattern | Keep/discard archive over the prompt, safely |
| 09 | Sandboxing & Safe Execution | Containarium / Nerve, checkpoints, safe-commit |
| 10 | Evaluation Harness | Eval-first, regression guards, variant-vs-baseline |
| 11 | Capstone — Production Agent | Wire it together + production checklist |
| 12 | Resources & Field Map | Annotated bibliography + glossary |
| 13 | Graduating to a Framework | Optional: when/how to adopt mem0, Pydantic AI, or the Claude Agent SDK on our backends |
| 14 | Framework Capstone — Shipping on deepagents | Build a self-improving code-fix agent on deepagents, keeping the eval gate yours |

> **Local model prep (16–32 GB Macs):** Module 02 includes a model-selection table — e.g. `Qwen2.5-Coder-7B-Instruct-4bit` + `nomic-embed-text-v1.5` on 16 GB, stepping up to a 14B model on 32 GB. The Claude/VibeProxy track still installs the local embedding model.
>
> **Optional framework track:** `scaffold/frameworks/` ships backend-aware drop-ins — [mem0](https://github.com/mem0ai/mem0) for memory and [Pydantic AI](https://github.com/pydantic/pydantic-ai) for the loop — both pointed at oMLX/VibeProxy via a custom `base_url`. Install with `pip install -e ".[frameworks]"`.

---

## Quick start

### 1. Install

```bash
git clone https://github.com/shaneliuyx/self-improving-agents-curriculum.git
cd self-improving-agents-curriculum
bash install.sh                              # tooling + scaffold
# also drop the notes into your Obsidian vault:
VAULT_DIR="/path/to/your/vault" bash install.sh
```

> **Prerequisite — [`agentkit`](https://github.com/shaneliuyx/agentkit).** The lab agent is
> **built on agentkit**: `scaffold/lab_agent.py` is `agentkit.SelfImprovingAgent.from_config(...)`,
> and the lab's `memory` / `gates` / `evolve` / `skills` / `agent` modules delegate to it. Install
> it first (it is not on PyPI — use the git URL):
> ```bash
> pip install "git+https://github.com/shaneliuyx/agentkit"
> ```
> `scaffold/requirements.txt` also pins it, so `pip install -e scaffold` pulls it in automatically.

### 2. Start a backend

- **Local:** install [oMLX](https://omlx.ai), download a chat model (e.g. `Qwen2.5-Coder-7B-Instruct-MLX-4bit`)
  and an embedding model (`bge-m3-mlx-fp16`), click **Start Server** (`:8000`).
- **Claude MAX:** install [VibeProxy](https://github.com/automazeio/vibeproxy), sign in with
  your subscription (`:8317`). *(Note: using a subscription via proxy may violate provider ToS.)*

Even on the Claude track, keep oMLX running for **local embeddings**.

### 3. Run the lab

```bash
cd ~/self-improving-agent-lab
cp .env.example .env          # set AGENT_BACKEND=omlx or vibeproxy
./scripts/go                  # one ACT->RECORD->REFLECT->LEARN->VERIFY iteration
```

---

## Keeping the curriculum fresh — `/improve-curriculum`

The curriculum maintains itself by applying its own thesis to itself. In Claude Code:

```
/improve-curriculum
```

This runs **GATHER → REFLECT → LEARN → VERIFY → SHIP**: it calls the
[`last30days`](https://github.com/mvanhorn/last30days-skill) skill (or `tools/refresh-research.sh`)
for fresh sources, gap-analyzes them against the current notes, applies **sourced, additive**
updates in parallel ([`tools/improve-workflow.js`](tools/improve-workflow.js)), audits
consistency (wikilinks, Mermaid, citations, `py_compile`), and pushes. Every edit must cite a
real source — the curriculum's own anti-"recursive-drift" rule.

> Requires the `last30days` plugin and Python 3.12+ for the research step.

---

## Grounding

This material is built from real signal surfaced in May 2026 — including the
[Darwin Gödel Machine](https://arxiv.org/abs/2505.22954),
[SkillOS](https://arxiv.org/abs/2605.06614),
[Komi-learn](https://github.com/kurikomi-labs/komi-learn),
the [agent-seed harness](https://github.com/B67687/agentic-workflows/pull/82),
the NousResearch [rule-priority-hierarchy finding](https://github.com/NousResearch/hermes-agent/issues/29652),
and the r/AI_Agents [skeptic thread](https://www.reddit.com/r/AI_Agents/comments/1taei9m/stop_building_ai_agents/).
Full provenance in [`research/`](research/).

## License

[MIT](LICENSE) © 2026 shaneliuyx
