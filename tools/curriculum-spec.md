# SHARED SPEC — "Building Self-Improving Agents" curriculum (READ FULLY)

You are authoring ONE note in a 13-note Obsidian curriculum. This file is the shared
contract: research facts, backend facts, Obsidian conventions, the full note list (for
wikilinks), and the house style. Obey it exactly. Your specific note spec is in your prompt.

Audience: an intermediate developer on an Apple-Silicon Mac who CANNOT call paid LLM APIs
directly. They use ONE of two backends:
  (A) LOCAL — oMLX (Apple Silicon MLX inference server)
  (B) Claude MAX subscription via VibeProxy (a local OAuth proxy)
Every code example MUST work on both backends via a single OpenAI-compatible `base_url` swap.

============================================================
## BACKEND FACTS (use these EXACT details; do not invent ports)
============================================================
- oMLX: native macOS menu-bar server, Apple Silicon only. OpenAI-compatible at
  `http://localhost:8000/v1` (`/v1/chat/completions`) AND Anthropic-compatible at
  `http://localhost:8000/v1/messages`. Serves text LLMs, VLMs, EMBEDDING models, and
  rerankers (auto-discovered from model subdirectories). Admin chat UI at
  `http://localhost:8000/admin/chat`. Repo: https://github.com/jundot/omlx  Site: https://omlx.ai
- VibeProxy: macOS menu-bar app, Apple Silicon only. Routes your Claude Code / ChatGPT /
  Gemini SUBSCRIPTION (OAuth, no API key) through a LOCAL proxy on `http://localhost:8317`.
  OpenAI- and Anthropic-compatible. Adds extended-thinking support via model-name suffix.
  Repo: https://github.com/automazeio/vibeproxy  ToS caveat: using a subscription via proxy
  may violate provider ToS — state this once, neutrally, where relevant.
- CRITICAL ARCHITECTURE FACT: VibeProxy exposes CHAT ONLY — there is NO embeddings endpoint
  on the Claude subscription. oMLX DOES serve embeddings locally. Therefore the memory/vector
  layer ALWAYS uses a LOCAL embedding model (via oMLX `/v1/embeddings` or sentence-transformers),
  even when generation runs through VibeProxy. Generation backend = swappable; embeddings = local.
- ECONOMICS: these backends are RATE-LIMITED, not per-token-metered. Many-call loops
  (reflection, critique, keep/discard, N-sample voting) are ~free in dollar terms but bounded by
  rate limits + local throughput. Design for throughput/rate-limits, not token cost. Contrast
  this explicitly with the paid-API mental model where each reflective call costs money.
- Unified client (canonical snippet to reuse/reference, do not contradict):
  ```python
  # backends/adapter.py — one client, both backends
  import os
  from openai import OpenAI  # OpenAI SDK speaks to any OpenAI-compatible server
  BACKENDS = {
      "omlx":      {"base_url": "http://localhost:8000/v1", "model": os.getenv("OMLX_MODEL", "qwen2.5-coder-7b")},
      "vibeproxy": {"base_url": "http://localhost:8317/v1", "model": os.getenv("VIBE_MODEL", "claude-sonnet-4-5-20250929")},
  }
  def make_client(backend=None):
      b = BACKENDS[backend or os.getenv("AGENT_BACKEND", "omlx")]
      # Local servers ignore the key; VibeProxy uses OAuth under the hood, so a placeholder is fine.
      return OpenAI(base_url=b["base_url"], api_key=os.getenv("LLM_API_KEY", "not-needed")), b["model"]
  ```
- Embeddings snippet (always local):
  ```python
  emb = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")  # oMLX
  v = emb.embeddings.create(model="Qwen3-Embedding-0.6B-4bit-DWQ", input="text").data[0].embedding
  ```

============================================================
## RESEARCH GROUNDING (cite as inline markdown links [name](url); these are the field's May-2026 signals)
============================================================
PAPERS / RESEARCH
- Darwin Gödel Machine (DGM) — self-rewriting coding agents validated on benchmarks; 20%→50% SWE-bench: https://arxiv.org/abs/2505.22954
- SkillOS: Learning Skill Curation for Self-Evolving Agents: https://arxiv.org/abs/2605.06614
- Muse-Autoskill: Self-Evolving Agents via Skill Creation and Memory: https://arxiv.org/abs/2605.27366
- Continual Harness: Online Adaptation for Self-Improving Foundation Agents: https://arxiv.org/abs/2605.09998
- SIA: Self Improving AI with Harness and Weight Updates: https://arxiv.org/abs/2605.27276
- Experiential Reflective Learning (ERL): https://arxiv.org/pdf/2603.24639
- Position: Truly Self-Improving Agents Require Intrinsic Metacognitive Learning: https://openreview.net/forum?id=4KhDd0Ozqe
- MemEvolve / EvolveLab (meta-evolution of agent memory): https://arxiv.org/pdf/2512.18746
PROJECTS / TOOLS (Show HN + GitHub, May 2026)
- agent-seed — minimal self-improving harness (GOAL.md motto + scripts/go iteration protocol + AGENTS.md operating contract + scripts/commit safe wrapper + CHANGELOG.md): https://github.com/B67687/agentic-workflows/pull/82
- Autodidact — self-evolving LOCAL-FIRST AI agent: https://github.com/BuffaloTechRider/Autodidact
- Airlock — self-upgrading compiled AI agents: https://github.com/airlockrun/airlock/
- Komi-learn — continuous memory + self-improvement for coding agents: https://github.com/kurikomi-labs/komi-learn
- mem0 — open-source memory layer for agents (hosted + self-host): https://github.com/mem0ai/mem0
- Containarium — self-hosted MCP-native sandbox for AI agents: https://github.com/footprintai/Containarium
- Nerve — self-hosted runtime for AI agents: https://github.com/ClickHouse/nerve
- Lite-Harness — self-hosted Cursor-style agents using Claude Code/OpenCode: https://github.com/LiteLLM-Labs/lite-harness
- Ivy Tendril — orchestrator: plan-based lifecycle with VERIFICATION GATES + self-improving memory; manages Claude Code/Codex/Copilot; local-first: https://github.com/yeaight7/awesome-ai-devtools/pull/3
- SIA (open source): https://github.com/hexo-ai/sia
- "What 1k Harness Experiments Taught Me About Self-Improving Agents" (henrypan): https://www.henrypan.com/blog/2026-05-25-self-improvement-harness/
- Strands — building self-extending CLI tools (AWS): https://aws.amazon.com/blogs/devops/building-self-extending-cli-tools-with-aws-strands/
- mem0 — agent memory layer (used as optional drop-in): https://github.com/mem0ai/mem0
- Pydantic AI — typed agent framework (optional loop drop-in): https://github.com/pydantic/pydantic-ai
- LangGraph — agent orchestration: https://github.com/langchain-ai/langgraph
- OpenAI Agents SDK: https://github.com/openai/openai-agents-python
- CrewAI — multi-agent framework: https://github.com/crewAIInc/crewAI
- Strands Agents (AWS): https://github.com/strands-agents/sdk-python
- Claude Agent SDK (used by SIA, Nerve): https://github.com/anthropics/claude-agent-sdk-python
- Arize — self-improving agent on a context graph of human disagreement: https://arize.com/blog/self-improving-agent-with-context-graph/
- Claude Managed Agents — self-hosted sandboxes + MCP tunnels: https://claude.com/blog/claude-managed-agents-updates
KEY PRODUCTION FINDING (NousResearch hermes-agent issue #29652) — the "rule priority hierarchy":
  L0 (Core, non-overridable identity) / L1 (Prompt) / L2 (deterministic no_agent script) / L3 (Global safety).
  Production verdict: "Layer 1 (Prompt) alone failed" — agents skipped explicit instructions; teams moved
  deterministic steps to L2 scripts. URL: https://github.com/NousResearch/hermes-agent/issues/29652
COMMUNITY REALITY CHECK (Reddit r/AI_Agents "Stop building AI agents", 1,447 upvotes):
  - Most "agents" shipping to business are just automations + one LLM call. Decision framework:
    (1) can you draw it as clear steps? -> automation. (2) >5 branches with unpredictable inputs? -> maybe agent.
    (3) high cost of worst-case wrong answer? -> automation. (4) compliance will review it? -> automation, full stop.
  - Maintenance burden kills projects ("3am Slack message when the agent approves the wrong invoices").
  - Model routing: don't default to flagship for every call; cheaper/older models often match at far lower cost
    (this maps to LOCAL model routing here — use a small oMLX model for cheap steps, Claude/large for hard steps).
  - Human-in-the-loop on the final execution step "saves 90% of the headache".
  URL: https://www.reddit.com/r/AI_Agents/comments/1taei9m/stop_building_ai_agents/

============================================================
## THE CANONICAL LOOP (every note should be consistent with this vocabulary)
============================================================
ACT -> RECORD -> REFLECT -> LEARN, gated by VERIFY:
  ACT: agent performs a task (the baseline loop, Module 03).
  RECORD: capture the full trajectory (Module 04 memory).
  REFLECT: critique the trajectory, extract heuristics/lessons (Module 05).
  LEARN: update memory / write a reusable skill / modify own prompt-or-code (Modules 06, 08).
  VERIFY: external evaluation gates every LEARN step to prevent "recursive drift" (Module 07, 10).
Three "camps" of self-improvement: (1) code/weight self-modification (DGM, SIA), (2) memory+skill
accumulation (SkillOS, Komi-learn, agent-seed), (3) the skeptic's "mostly you want an automation".
The curriculum's thesis: for subscription/local builders, camp (2) + strong VERIFY is the pragmatic
sweet spot; camp (1) is reserved for narrow, benchmarkable, sandboxed sub-problems.

============================================================
## RUNNABLE SCAFFOLD (referenced by notes; lives OUTSIDE the vault)
============================================================
Path: /Users/yuxinliu/self-improving-agent-lab
Layout (notes may reference these paths):
  GOAL.md, AGENTS.md, README.md, CHANGELOG.md, .env.example, requirements.txt, config.py
  backends/adapter.py, backends/router.py
  agent/loop.py, agent/tools.py
  memory/store.py
  reflection/reflect.py
  skills/library.py, skills/SKILLS/
  verification/gates.py
  evolve/loop.py, evolve/archive/
  evals/tasks.py, evals/run.py
  scripts/go, scripts/commit
When a note has a hands-on lab, reference the relevant scaffold file by path and show the key code inline.

============================================================
## OBSIDIAN + HOUSE STYLE (MANDATORY)
============================================================
- Output is a single Markdown note written via the Write tool to the EXACT absolute path in your prompt.
- Start with YAML frontmatter:
  ---
  title: "<the note title>"
  tags: [self-improving-agents, curriculum, <2-4 topical tags>]
  module: <NN>
  updated: 2026-05-31
  ---
- After frontmatter: an H1 `# <NN> · <Title>`, then a one-paragraph "**What you'll learn**" lead-in,
  then a `> [!info] Prerequisites` Obsidian callout listing the wikilinks to prerequisite modules.
- Use Obsidian callouts liberally: `> [!tip]`, `> [!warning]`, `> [!example]`, `> [!note]`, `> [!danger]`,
  `> [!question]`. Use them for pitfalls, key insights, and checkpoints.
- WIKILINKS: link to other notes as [[<exact filename without .md>]]. The exact filenames are listed below.
  Your prompt tells you which links are REQUIRED (prereqs, next, cross-refs). Always end the note with a
  `## Navigation` section: `← [[prev]] · [[00 - Curriculum Map]] (home) · [[next]] →`.
- DIAGRAMS: include the diagrams your prompt requires, as fenced ```mermaid blocks. They MUST be
  syntactically valid Mermaid. Prefer: flowchart TD/LR, sequenceDiagram, stateDiagram-v2, classDiagram,
  mindmap, graph. Keep node labels short; avoid parentheses/quotes inside node labels that break parsing
  (use plain words or escape). Every diagram needs a one-line caption under it in italics.
- CITATIONS: cite research as inline [name](url) links using the RESEARCH GROUNDING URLs above. Do NOT
  fabricate URLs. No "Sources:" block at the end — links are inline.
- CODE: Python, runnable, consistent with the unified adapter above. Show `AGENT_BACKEND=omlx` vs
  `AGENT_BACKEND=vibeproxy` where relevant. Real, complete snippets — not pseudocode — for labs.
- Each note must include: learning objectives (checklist), the concept with a diagram, a HANDS-ON LAB
  (concrete steps + code referencing the scaffold), common PITFALLS (callouts), and a CHECKPOINT
  (`> [!question] Checkpoint` with 3-5 self-test questions). Target 250-500 lines of rich content.
- VOICE: clear, technical, example-driven. Use " - " not em-dashes. No marketing fluff.

============================================================
## FULL NOTE LIST (exact filenames — use for wikilinks)
============================================================
00 - Curriculum Map
01 - What Self-Improving Means
02 - Backends - oMLX and VibeProxy
03 - The Minimal Agent Loop
04 - Memory Systems
05 - Reflection and Self-Correction
06 - Skill Acquisition and Curation
07 - Verification Gates and Layered Control
08 - Self-Modification - The DGM Pattern
09 - Sandboxing and Safe Execution
10 - Evaluation Harness
11 - Capstone - Production Agent
12 - Resources and Field Map
13 - Graduating to a Framework
