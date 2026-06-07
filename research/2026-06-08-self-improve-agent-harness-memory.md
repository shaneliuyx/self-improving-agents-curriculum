# Research refresh - 2026-06-08

Focus: **self-improve agent and harness and memory**
Engine: `/last30days` (last30days v3) - 70 items across GitHub (24), Hacker News (24), Reddit (19), YouTube (3); X absent (no auth this run). Raw dump: `~/Documents/Last30Days/building-self-improving-agents-self-improve-agent-and-harness-and-memory-raw-v3.md` (+ appended WebSearch supplements).

All numbers below were traced to their source artifact and re-verified with a second WebSearch before being recorded (curriculum anti-drift rule applied to itself).

## Headline shift this window: "harness engineering" is now a named paradigm

The dominant 30-day signal is the crystallization of **harness engineering** as the third phase of agent engineering, after prompt engineering and context engineering. The harness = the code AROUND the LLM (what you retrieve, how you format it, when you summarize, which state you discard).

- OpenAI, "Harness engineering: leveraging Codex in an agent-first world" - https://openai.com/index/harness-engineering/ . ~1M LOC and ~1,500 PRs by 3 (then 7) engineers driving Codex at ~3.5 PRs/eng/day. "Humans steer. Agents execute." "Give Codex a map, not a 1,000-page instruction manual."
- OpenAI, "Unlocking the Codex harness: how we built the App Server" - https://openai.com/index/unlocking-the-codex-harness/
- O'Reilly Radar, "Agent Harness Engineering" - https://www.oreilly.com/radar/agent-harness-engineering/
- "Agent Harness Engineering: A Survey" (OpenReview) - https://openreview.net/pdf?id=eONq7FdiHa
- awesome-harness-engineering (ai-boost) - https://github.com/ai-boost/awesome-harness-engineering

## Measured: automated harness optimization beats hand-engineering, no weight updates

- **Meta-Harness** (Stanford IRIS Lab / MIT / KRAFTON; NOT a Meta paper - verify this attribution) - https://arxiv.org/html/2603.28052v1 ; artifact https://github.com/stanford-iris-lab/meta-harness-tbench2-artifact
  - 76.4% on Terminal-Bench 2.0 with Claude Opus 4.6, beating hand-engineered Terminus-KIRA (74.7%), #2 on the leaderboard. 37.6% on Haiku 4.5 (beats Goose 35.5%).
  - Harness choices swing the same benchmark by up to **6x**. All without touching model weights.
  - Maps to: **10 - Evaluation Harness** (Terminal-Bench-2 as an external benchmark; automated harness search), and the harness-engineering framing in **03 - The Minimal Agent Loop**.

## Self-modification frontier

- **HyperAgents** (Meta FAIR), "When Agents Engineer Their Own Harness" - https://arxiv.org/pdf/2603.19461 ; coverage https://venturebeat.com/orchestration/meta-researchers-introduce-hyperagents-to-unlock-self-improving-ai-for-non-coding-tasks
  - DGM-Hyperagents: the meta-agent rewrites its own code, so the mechanism that GENERATES improvements is itself improved ("metacognitive self-modification"). Extends self-improvement beyond coding to non-coding tasks.
  - Maps to: **08 - Self-Modification - The DGM Pattern** (direct extension of DGM).
- **SIA integration into Hermes** - https://github.com/NousResearch/hermes-agent-self-evolution/issues/99 (SIA: https://github.com/hexo-ai/sia). A live proposal to wire SIA's harness+weight self-improvement into the Hermes self-evolving agent as a skill. Maps to **08** and **13/14 (framework)**.
- **Peter Norvig joins $4B "Recursive" effort** (HN) - field-map signal for **12 - Resources and Field Map**.

## The critical caveat (highest-value finding for the thesis)

- **AI Agents Hit Self-Improvement Wall After One Pass** - https://aiweekly.co/alerts/ai-agents-hit-self-improvement-wall-after-one-pass
  - Across 1,000+ experiments, agents proposed ONE structural harness improvement but consistently failed to **compound** it. The plateau is attributed to agents lacking an internal **self-model** that explains *why* the first change worked - an architectural gap scaling does not close.
  - This is a concrete ceiling on "self-improvement compounds with capability" - at iteration one. Strongly reinforces the curriculum thesis (camp 2 + strong VERIFY > naive camp 1) and the role of VERIFY in **07** / **10**, plus a caveat callout in **08**.
- **The verifiability constraint** (o-mega 2026 guide) - https://o-mega.ai/articles/self-improving-ai-agents-the-2026-guide - self-improvement is reliable only where outcomes are objectively verifiable (code compiles, proof valid, faster algorithm). Reinforces **07 - Verification Gates**.

## Memory

- **mem0, "State of AI Agent Memory 2026"** - https://mem0.ai/blog/state-of-ai-agent-memory-2026 - memory as a first-class architectural component; token-efficient memory via single-pass hierarchical extraction + multi-signal retrieval. Maps to **04 - Memory Systems**.
- **IBM Technology, "The Four Types of Memory Every AI Agent Needs"** (YouTube, 120K views) - working/episodic/semantic/procedural taxonomy. Maps to **04**.
- **r/ClaudeWorkflows "Separating Memory, Policy, and Audit"** - https://www.reddit.com/r/ClaudeWorkflows/comments/1tx5xfc/workflow_architectural_pattern_separating_memory/ - practitioner layering pattern. Maps to **04** / **07**.

## Harness reliability patterns (practitioner)

- **Mungr: Gated Agent Harness Architecture** - https://www.reddit.com/r/ClaudeWorkflows/comments/1txmqdj/workflow_mungr_a_gated_agent_harness_architecture/ - gating as the reliability primitive. Maps to **07**.
- **Empirica: harness for epistemic awareness + self-correcting investigate-then-act** - https://www.reddit.com/r/ClaudeWorkflows/comments/1ttxt5d/workflow_empirica_an_opensource_ai_harness_for/ - Maps to **05 - Reflection and Self-Correction** / **07**.

## Proposed change list (additive, sourced) - fed to improve-workflow.js Analyze pass

| Note | Addition | Source(s) |
|------|----------|-----------|
| 00 Curriculum Map | one-line "prompt -> context -> harness engineering" framing | OpenAI, O'Reilly |
| 03 Minimal Agent Loop | "the loop you build IS the harness"; 70%-outside-the-model + up-to-6x-swing framing | OpenAI, Meta-Harness, O'Reilly survey |
| 04 Memory Systems | mem0 state-of-memory; IBM four-types taxonomy; memory/policy/audit separation | mem0, IBM, r/ClaudeWorkflows |
| 05 Reflection | Empirica epistemic self-correction; verifiability constraint | r/ClaudeWorkflows, o-mega |
| 07 Verification Gates | Mungr gating; verifiability constraint reinforcement | r/ClaudeWorkflows, o-mega |
| 08 DGM Pattern | HyperAgents metacognitive self-modification; SIA-into-Hermes; **one-pass wall caveat** | arxiv 2603.19461, hermes #99, aiweekly |
| 10 Evaluation Harness | Meta-Harness automated harness search; Terminal-Bench 2.0 | arxiv 2603.28052 |
| 12 Field Map | awesome-harness-engineering; survey; OpenAI posts; HyperAgents; Meta-Harness; Recursive; Hermes self-evolution | all above |

Scaffold (minimal, additive): a comment in `evolve/loop.py` noting the one-pass compounding ceiling and that VERIFY must gate every iteration; optional memory/policy/audit-separation note in `memory/store.py`.

## Addendum - sources surfaced by the LEARN workflow (verified post-hoc)

The improve-workflow.js Analyze pass surfaced one paper NOT in the last30days dump above; it was independently verified via WebSearch before being kept (no unsourced edits):

- **"Rethinking Continual Experience Internalization for Self-Evolving LLM Agents"** - https://arxiv.org/abs/2606.04703 - submitted 2026-06-03 (Renmin University / Beihang / Meituan). Under multi-iteration experience learning, existing methods suffer **progressive capability collapse**, not compounding gain; **principle-level** experience (distilled rules) is more durable than **instance-level** (raw traces); **step-wise injection** beats global batch injection. Added to **05 - Reflection and Self-Correction**. (Author attribution dropped from the note - search returned institutions, not a confirmable first author.)

The workflow applied only 1 of the proposed changes (to note 05); the remaining additive edits in the table above were authored directly with verified citations (notes 03, 08, 10, 12).
