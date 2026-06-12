# Research Refresh — Loop / Harness Engineering (2026-06-12)

Focus argument: **"loop engineering"**. Gathered via `/last30days` engine (degraded - no
Reddit/X auth on this machine, so social signal was thin; GitHub + YouTube + RedditKeyless only)
plus targeted WebSearch supplements. The WebSearch channel carried the high-signal evidence and
is the basis for the change list below. Every claim maps to a real URL.

## Headline: "loop engineering" / "harness engineering" is a new, nameable framing (2026)

The field has coalesced, in the last ~30 days, around a vocabulary the curriculum does not yet use
by name: **harness engineering** (and its operational sibling **loop engineering**). The thesis is
adjacent to our own (ACT -> RECORD -> REFLECT -> LEARN -> VERIFY), but the 2026 framing sharpens two
points the curriculum should adopt explicitly:

1. **Agent = model + harness.** The harness is every piece of code, config, and execution logic that
   is *not* the model: the loop, tools, middleware, memory, skills, verification. Differentiation in
   2026 is the harness, not the model.
   - [LangChain - Improving Deep Agents with harness engineering](https://blog.langchain.com/improving-deep-agents-with-harness-engineering/)
   - [LangChain deepagents docs - Harness capabilities](https://docs.langchain.com/oss/python/deepagents/harness)
   - [explainx.ai - Agent harness engineering: when the model stays fixed and the scaffolding wins](https://explainx.ai/blog/agent-harness-engineering-terminal-bench-langchain-2026)
   - **Concrete number:** LangChain lifted a coding agent from **52.8% -> 66.5% on Terminal Bench 2.0**
     (Top 30 -> Top 5) with the **model fixed** (gpt-5.2-codex) - pure harness engineering.

2. **Loop engineering is the operational layer above prompting.** Progression named by multiple
   sources: autocomplete (2023) -> prompting (2024) -> parallel agents (2025) -> **writing loops that
   do the prompting themselves (2026)**. A loop "is not a prompt - it is a recurring process with
   memory, verification, and boundaries." Verification is the load-bearing part: "without
   verification, threads end prematurely and loops spin forever."
   - [explainx.ai - Loop Engineering: Design Coding Agent Loops That Run While You Sleep (2026 Guide)](https://explainx.ai/blog/loop-engineering-coding-agents-claude-code-guide-2026)
   - [Louis Bouchard - Loop Engineering Explained](https://www.louisbouchard.ai/loop-engineering/)
   - [Cobus Greyling - Loop Engineering Playbook (Jun 2026)](https://cobusgreyling.medium.com/loop-engineering-playbook-4460e01e88d8)
   - [claudefa.st - Claude Code Autonomous Loops: Ship Features While You Sleep](https://claudefa.st/blog/guide/mechanics/autonomous-agent-loops)

## New papers (self-improving harness, directly on-thesis)

- **Self-Harness: Harnesses That Improve Themselves** (arXiv:2606.09498, 2026-06-08). An LLM agent
  improves its *own* operating harness with no human engineer and no stronger external agent. Loop =
  **Weakness Mining** (find model-specific failure patterns from execution traces) -> **Harness
  Proposal** (diverse, minimal harness edits tied to those failures) -> **Proposal Validation**
  (accept an edit only after regression testing). Maps cleanly onto our REFLECT -> LEARN -> VERIFY,
  and is a *harness-level* (not weight-level) analogue to DGM (Module 08).
  https://arxiv.org/abs/2606.09498

- **Retrospective Harness Optimization (RHO): Improving LLM Agents via Self-Preference over
  Trajectory Rollouts** (arXiv:2606.05922, 2026-06-04; CityU HK + MSR Asia). Self-supervised: optimizes
  the harness using only *past, unlabeled* trajectories - no ground-truth labels, no validation set.
  Selects a diverse coreset of hard tasks, re-solves in parallel, scores rollouts by self-validation +
  self-consistency, generates candidate harness updates, picks the best by **pairwise self-preference**.
  **Number: one retrospective pass lifts SWE-Bench Pro 59% -> 78%.** Repo: `wbopan/retro-harness`.
  This is RECORD -> REFLECT -> LEARN driven purely from the trajectory log (Module 04 + 05).
  https://arxiv.org/abs/2606.05922  ·  https://github.com/wbopan/retro-harness

- **Agentic Harness Engineering: Observability-Driven Automatic Evolution of Coding-Agent Harnesses**
  (arXiv:2604.25850). Observability/telemetry drives automatic harness evolution - reinforces the
  VERIFY-and-instrument theme (Module 07/10).
  https://arxiv.org/html/2604.25850v1

- **Natural-Language Agent Harnesses** (arXiv:2603.25723). Harness logic expressed in NL rather than
  code - a useful contrast point to the NousResearch L2 "deterministic no_agent script" production
  finding already in the spec.
  https://arxiv.org/pdf/2603.25723

## New tools / lists

- **awesome-harness-engineering** (GitHub `ai-boost/awesome-harness-engineering`) - curated list:
  tools, patterns, evals, memory, MCP, permissions, observability, orchestration. Strong addition to
  the Module 12 field map. https://github.com/ai-boost/awesome-harness-engineering
- **langchain-ai/deepagents** - "the batteries-included agent harness." Already the subject of Module
  14; the harness-capabilities docs + the Terminal-Bench result are fresh reinforcing citations.
  https://github.com/langchain-ai/deepagents
- **decodingai - Agentic Harness Engineering: LLMs as the New OS** (framing essay).
  https://www.decodingai.com/p/agentic-harness-engineering

## Backend-fit caveat (keep the curriculum's own economics framing)

The loop-engineering guides repeatedly warn that self-prompting loops "burn through millions of
tokens." For *this* curriculum's backends (local oMLX / Claude-MAX-via-VibeProxy) the binding
constraint is **rate-limits + local throughput**, not per-token dollars - the existing spec ECONOMICS
note already says this. When citing loop-engineering's cost warnings, reframe to "spin-forever /
throughput / rate-limit budget," not dollar cost. The "stopping condition + verifiable goal" advice
transfers unchanged and strengthens Module 07 (VERIFY gates) and Module 03 (loop budget).

## Proposed change list (additive, source-mapped) - for REFLECT/LEARN

- **00 - Curriculum Map**: one line naming "harness/loop engineering" as the 2026 umbrella term for
  what the curriculum teaches. (LangChain blog, explainx.ai)
- **01 - What Self-Improving Means**: add the autocomplete->prompting->parallel->loops progression and
  "agent = model + harness" framing; situate self-improvement as harness-level improvement.
  (explainx.ai loop guide; LangChain blog)
- **03 - The Minimal Agent Loop**: cite loop-engineering's "a loop is not a prompt - recurring process
  with memory + verification + boundaries"; reinforce stopping-condition/verifiable-goal. (explainx.ai)
- **05 - Reflection and Self-Correction**: add RHO - reflection over *unlabeled past trajectories* via
  self-preference (59->78 SWE-Bench Pro). (arXiv:2606.05922)
- **07 - Verification Gates**: Self-Harness Proposal-Validation (regression-gated harness edits) as a
  named external-gate pattern; "without verification loops spin forever." (arXiv:2606.09498; explainx.ai)
- **08 - Self-Modification (DGM)**: add Self-Harness as the *harness-level* sibling of DGM's
  weight/code self-modification - same accept-after-test gate, lower blast radius. (arXiv:2606.09498)
- **10 - Evaluation Harness**: observability-driven harness evolution; Terminal Bench 2.0 52.8->66.5
  harness-only result as a motivating eval-moves-the-needle datapoint. (arXiv:2604.25850; LangChain)
- **12 - Resources and Field Map**: add awesome-harness-engineering, Self-Harness, RHO, the loop-
  engineering guides. (all URLs above)
- **13/14 - Framework / deepagents**: deepagents = "batteries-included agent harness"; harness-caps
  docs + Terminal Bench number. (deepagents docs/repo; LangChain blog)
- **SPEC (curriculum-spec.md) RESEARCH GROUNDING**: append Self-Harness, RHO, Agentic Harness
  Engineering, NL Agent Harnesses, awesome-harness-engineering, LangChain harness blog, explainx loop
  guide - so future runs cite from a vetted list.

No scaffold code change is strictly required (the loop/verify scaffold already embodies the pattern);
optional: a one-line comment in `evolve/loop.py` or `verification/gates.py` pointing at Self-Harness/RHO
as the literature for "propose harness edit -> regression-gate -> keep/discard." No new module justified.
