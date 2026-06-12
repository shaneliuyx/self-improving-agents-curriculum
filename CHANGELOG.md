# Changelog

All notable changes to the curriculum and scaffold. The `/improve-curriculum` command
appends a dated entry here each time it refreshes the material from new sources.

## 2026-06-12 — Self-improving the harness: Self-Harness + RHO (curriculum refresh, focus: loop engineering)

Additive, sourced refresh from `/improve-curriculum` (focus argument: **loop engineering**). The `/last30days` engine ran degraded on this machine (no Reddit/X auth, so social signal was thin - GitHub/YouTube/RedditKeyless only); the high-signal evidence came from WebSearch supplements, recorded in `research/2026-06-12-loop-engineering-refresh.md`. All hard checks green: 15 notes / 30 mermaid blocks audited, 0 broken wikilinks, 0 bad mermaid keywords, `py_compile` clean on both scaffold copies, every new URL traced to a real search result (no fabricated links). The "harness/loop engineering" framing was *already* absorbed in the 2026-06-08 refresh, so this pass adds only the genuine delta - two June-2026 papers that were absent everywhere. Notes touched: 03, 05, 08, 12 (+ spec research grounding).

- **08 - Self-Modification - The DGM Pattern.** New callout "Self-Harness - self-modification at the harness layer": an agent improves its own harness with no human and no stronger external model, via Weakness Mining -> Harness Proposal -> Proposal Validation (regression-gated). Framed as the harness-layer sibling of DGM - same accept-after-test gate, smaller blast radius. Source: [Self-Harness](https://arxiv.org/abs/2606.09498) (2026-06-08).
- **05 - Reflection and Self-Correction.** New callout on RHO: runs the REFLECT step over the trajectory log with no labels and no validation set, scoring rollouts by pairwise self-preference; one retrospective pass lifts SWE-Bench Pro 59% -> 78%. Ties RECORD -> REFLECT to the recursive-drift caution (self-preference is internal, so gate it externally). Source: [Retrospective Harness Optimization](https://arxiv.org/abs/2606.05922) (2026-06-04), code [wbopan/retro-harness](https://github.com/wbopan/retro-harness).
- **03 - The Minimal Agent Loop.** Extended the "loop you are building IS the harness" callout to name *loop engineering* - the scheduling/stopping-condition layer that turns a one-shot run into a recurring, verifiable process; reinforces why the VERIFY gate is load-bearing for unattended loops. Source: [explainx.ai loop-engineering guide](https://explainx.ai/blog/loop-engineering-coding-agents-claude-code-guide-2026).
- **12 - Resources and Field Map.** Two new bibliography rows (Self-Harness, RHO) and two new mindmap nodes under "Harnesses and Evals".
- **tools/curriculum-spec.md.** RESEARCH GROUNDING extended with Self-Harness and RHO so future refresh runs cite from a vetted list.

## 2026-06-08 — Harness engineering as the named paradigm + the compounding ceiling (curriculum refresh)

Additive, sourced refresh from `/improve-curriculum` (focus: self-improve agent + harness + memory). Driven by the last-30-days research dump in `research/2026-06-08-self-improve-agent-harness-memory.md` plus independently-verified WebSearch supplements. All hard checks green: 0 broken wikilinks, balanced mermaid/code fences, `py_compile` clean, every new URL traced to a real source (no fabricated links). Notes touched: 03, 05, 08, 10, 12.

- **03 - The Minimal Agent Loop.** New callout "The loop you are building IS the harness" - frames prompt/tool-schema/dispatcher/trajectory as the agent's harness and introduces "harness engineering" as the 2026 third phase after prompt and context engineering. Sources: [O'Reilly Radar](https://www.oreilly.com/radar/agent-harness-engineering/), [OpenAI harness engineering](https://openai.com/index/harness-engineering/).
- **05 - Reflection and Self-Correction.** New callout on principle-level vs instance-level experience: under multi-iteration learning, raw-trace storage causes progressive capability collapse; distilled (principle-level) heuristics + step-wise injection are more durable. Source: [Rethinking Continual Experience Internalization](https://arxiv.org/abs/2606.04703) (2026-06-03, verified). Reinforces the "store distilled heuristics, inject at the relevant step" recommendation.
- **08 - Self-Modification - The DGM Pattern.** Added HyperAgents (Meta FAIR) metacognitive self-modification - the meta-agent rewrites its own improvement loop ([arxiv 2603.19461](https://arxiv.org/pdf/2603.19461)); a SIA-into-Hermes integration pointer ([hermes-agent-self-evolution #99](https://github.com/NousResearch/hermes-agent-self-evolution/issues/99)); and the **compounding-ceiling caveat** - across [1,000+ harness experiments](https://aiweekly.co/alerts/ai-agents-hit-self-improvement-wall-after-one-pass) agents make one improvement then fail to compound it for lack of a self-model. This is the most important teaching addition: it bounds the keep/discard loop's expected payoff.
- **10 - Evaluation Harness.** Added Meta-Harness (Stanford IRIS Lab / MIT / KRAFTON, [arxiv 2603.28052](https://arxiv.org/html/2603.28052v1)): an agent optimizes the harness around a frozen model, 76.4% on Terminal-Bench 2.0 (Opus 4.6), beating hand-engineered harnesses with no weight updates; harness choices alone swing the same benchmark up to 6x - the eval harness is what keeps that search from becoming recursive drift.
- **12 - Resources and Field Map.** New bibliography rows: HyperAgents, Meta-Harness, [Agent Harness Engineering survey](https://openreview.net/pdf?id=eONq7FdiHa), [awesome-harness-engineering](https://github.com/ai-boost/awesome-harness-engineering), the two OpenAI harness posts, and the one-pass-wall community finding.
- **Tooling de-drift.** `tools/improve-workflow.js` had dead hardcoded paths (`第二大脑`, root-level repo) and was missing note 14; corrected VAULT/SPEC/LAB roots, added note 14, fixed note-count strings, bumped the update-date stamp. `tools/curriculum-spec.md` note list extended to include note 14.

## 2026-06-01 — Resilience, observability, state-durability + containment/injection defense (scaffold)

Turns the remaining note-11 Harness Completeness Checklist gaps (rows 1, 10, 11) toward "Implemented" and hardens the loop against the failure modes in the CREAO/Hermes agent-harness article. The behavior-test regression guard grew 11 → 15 checks, all green on oMLX + VibeProxy.

- **Resilience (Stage 5).** `backends/adapter.py` wraps every model call in `_with_retry` — capped exponential backoff with deterministic jitter for the *retryable* class (429 / 5xx / timeout / connection drop) and immediate raise for the *fatal* class (auth / bad-request), so a 400 never burns rate-limit headroom. A per-request `LLM_TIMEOUT_S` (default 60) stops a hung local model from blocking forever. `agent/loop.py` accumulates `total_tokens` from `response.usage` (TPM/RPM visibility). Retryable-vs-fatal taxonomy taught in note 02 §5.
- **Observability + state durability (Stages 5–6).** New `agent/runlog.py` (append-only JSONL per-step run log with token telemetry) and `agent/replay.py` (read-only time-travel trace over one recorded run — distinct from eval-replay). `agent/loop.py` gains an optional `log=True` and a cooperative `KeyboardInterrupt` handler that finalizes a partial trajectory cleanly (`stop_reason="interrupted"`) instead of losing it. `logs/` gitignored. New behavior check: "runlog + replay". Note-11 checklist row 10 (Observability) → Implemented.
- **Containment + injection defense (Stage 7) — the deterministic safety floor.** `verification/gates.py` gains `requires_sandbox()` / `_SANDBOX_TOKENS` and an always-on `_gate_containment` wired into `verify()` *before* the regression gate, so a proposal touching filesystem/subprocess/network/exec ESCALATEs for human review *regardless of eval score* (the LLM safety gate is promptable and demo-disabled; this floor is free, deterministic, non-overridable). `agent/quarantine.py` frames untrusted tool output as DATA (framing, not filtering) before it re-enters the conversation; `agent/loop.py` quarantines both tool paths while the trajectory keeps the raw result. `agent/net_guard.py` validates backend URLs against a loopback egress allowlist at startup (config-mutation exfiltration defense). New `SAFE-001` eval + 3 behavior checks (containment, injection-quarantine, net_guard). **Honest finding:** Claude resists the injection, the 3B local model still complies — framing is necessary, not sufficient; the deterministic capability layer is what actually contains the blast radius. Note-11 §4.4 rewritten; checklist row 11 (Security) → Implemented.

## 2026-06-01 — Close the self-improvement core + write→verify→recover (scaffold)

Turns two "GAP — exercise" rows of the note-11 Harness Completeness Checklist into "Implemented", with behavior-test regression guards (gate grew 9 → 11 checks, all green on oMLX + VibeProxy).

- **Memory is no longer write-only (Stage 3).** `memory/store.py` gains `inject_context(query, k)` (retrieve top-k relevant lessons, format an injectable `<memory_context>` block, empty-safe) and `record_trajectory()`. `agent/loop.py::run_agent` now accepts `memory=` and injects retrieved lessons BEFORE acting, and `difficulty=` so routing is adaptive (honors `route_decision.model` - previously dropped). `scripts/go` passes `memory=store`; `evals/run.py` passes `difficulty=task.difficulty`. `.env.example` documents distinct `OMLX_SMALL_MODEL`/`OMLX_LARGE_MODEL` so routing is not a no-op. New behavior check: "memory injection (read-side)".
- **Write→verify→recover chain (Stage 4) - the article's flagship Claude-Code differentiator.** `agent/tools.py` gains `edit_file` (anchored old→new edit, unique-anchor validation, atomic temp+`os.replace` write, snapshot for rollback) and `run_tests` (pytest, output feeds back into the next turn = recovery loop). A capability-scoped `_safe_write`/`_assert_writable` denies writes to `verification/`/`scripts/`/`.git/`/`evals/` BY PATH before the file is read; `read_file` is hardened (Path.parents containment + `.env`/`.pem`/`.key` read blocked, closing a secret-exfiltration path). New behavior check: "write-verify-recover chain". Taught in note 09 §4.1 (anchored diffs vs full-overwrite); note 11 checklist rows updated.

## 2026-06-01 — Harness layer named + framework-capstone added (notes)

Motivated by the "agent harness" thesis (North@CreaoAI; [Anthropic masterclass](https://www.youtube.com/watch?v=efRIrLXoOVA) "the harness matters as much as the model"; [O'Reilly](https://www.oreilly.com/radar/agent-harness-engineering/)) and a full gap-analysis of the lab/curriculum against that checklist.

- **Note 00:** new "Three Layers: Brain / Harness / Agent" framing block - names the harness as a first-class layer and states the build-then-graduate arc.
- **Note 11:** new §4.0 "Harness Completeness Checklist" - 12-row audit mapping each harness subsystem to the lab file that implements it, or an honest "GAP - exercise" / "Out-of-scope" label.
- **Note 14 (NEW):** "Framework Capstone - Shipping on deepagents" - build a real self-improving code-fix agent on [deepagents](https://github.com/langchain-ai/deepagents) (24K stars), backend-swappable to oMLX/VibeProxy via a verified `ChatOpenAI(base_url=...)` swap. Primitive→framework mapping table; the external eval gate stays yours (never let the framework self-approve). Closes the build→buy arc opposite [[11]].
- **Drift fixes (notes now match the shipped lab API):** note 02 router (`get_model/TIER_*` → `route()/RouteDecision`), note 04 memory class-diagram (`search_all` → `add/search/get_recent`), note 10 eval runner (single-shot completion → drives the real `run_agent`).
- Code stages that turn the checklist's "GAP" rows into "implemented" (memory-retrieval, routing, write→verify→recover, resilience, containment) are tracked separately and land as scaffold changes, not in this notes-only commit.

## 2026-06-01 — Refresh from last-30-days sources (SkillOpt, SAMULE)

- **Note 06 (Skill Acquisition):** added [SkillOpt](https://arxiv.org/abs/2605.23904) (Microsoft,
  May 2026) - treats the skill document as the *trainable external state* of a frozen agent; a
  separate optimizer model proposes bounded add/delete/replace edits accepted only when they
  improve a held-out validation score. Reinforces the module's PROPOSE -> VALIDATE gate and the
  [[07 - Verification Gates and Layered Control]] thesis; best-or-tied on all 52 (model, benchmark,
  harness) cells including Claude Code, at zero added inference-time cost.
- **Note 05 (Reflection):** added [SAMULE](https://arxiv.org/abs/2509.20562) (EMNLP 2025) -
  multi-level reflection synthesis at micro (single-trajectory), meso (intra-task error taxonomy),
  and macro (cross-task transferable insight) levels; clarifies that only macro-level reflection
  yields the transferable lessons worth promoting into reusable skills.
- Additive, sourced edits only; wikilinks/mermaid/citations audited; scaffold `py_compile` green.
  Driving signal: last30days research + arXiv (2605.23904, 2509.20562).

## 2026-05-31 — Behavior eval extended (reflection, skill, verify-gate, DGM)

- **`evals/behavior_test.py` grown to 9 checks across two tiers:**
  - Backend-independent (run in CI, no LLM): the verify gate ACCEPT / REJECT-regression / REJECT-malformed
    logic (the keep/discard *decision*), and a Skill save -> load -> list round-trip.
  - Backend-dependent: tool use (`396` on both backends), embeddings, reflection -> `Lessons`,
    `propose_skill`, semantic `search_skills`, and DGM evolve **discard** (a worse variant is rejected by
    the gate).
- Verified live: **all 9 PASS** against oMLX + VibeProxy; the CI tier (2 checks) passes with no backend.
  The CI `behavior-eval` job now asserts real gate + persistence behavior, not just a skip.

## 2026-05-31 — Behavior-eval regression guard

- **New `evals/behavior_test.py`**: asserts the agent *executes* the calculator tool and returns `396`
  on every reachable backend (oMLX text-tool-call fallback + VibeProxy native `tool_calls`), and that
  `MemoryStore` ranks the right memory. Backends that are down are SKIPPED, so it is CI-safe. Verified
  live: all 3 checks PASS; skip path exits 0.
- **New CI job `behavior-eval`**: installs the scaffold and runs the eval - in CI it skip-passes and
  doubles as a full-stack import test (catching import regressions `py_compile` misses). Documented in note 10.

## 2026-05-31 — Baseline loop made oMLX-complete (text-tool-call fallback)

- **Verified `agent/loop.py` against oMLX** and found it relied solely on native `tool_calls`, which the
  local 7B model does not emit - it returns the call as text (`<tools>{...}</tools>`), so the tool never ran.
- **Added `_parse_text_tool_calls()`**: when there are no structured `tool_calls`, the loop now parses
  `<tools>` / `<tool_call>` / fenced-JSON / bare-JSON calls from the content, executes them, and feeds the
  observation back. Verified live: tool use returns `396` on **both** oMLX (text fallback) and
  VibeProxy/Claude (native, no regression). Documented in note 03; cross-linked from note 13.

## 2026-05-31 — All three framework adapters live-verified

- **`pydantic_ai_loop.py`** (pydantic-ai 1.104.0): returns `396` against VibeProxy/Claude via native tool-calling.
  Fixed its provider key to be backend-aware (`OMLX_API_KEY` for oMLX). Documented that **oMLX small
  models do not return structured `tool_calls`** - they emit the call as text - so native-tool-calling
  frameworks need a tool-capable backend or a larger local model.
- **`mem0_memory.py`** (mem0 2.0.4): verified on oMLX (local 7B extraction + `nomicai-modernbert-embed-base-bf16`
  embeddings + chroma) - `add` + `search` returned the right memory at 0.849 similarity. Updated to the
  mem0 2.x API (`search(query, filters={...}, top_k=...)`).

## 2026-05-31 — Claude Agent SDK fully verified (subscription path works)

- **Confirmed working**: with `claude-agent-sdk` 0.2.87 the adapter returns the correct answer
  (`17 * 23 + 5 = 396`) using the in-process calculate tool, on the Claude subscription.
- **Root cause of the earlier billing block**: an `ANTHROPIC_API_KEY` in the environment forces the
  bundled Claude Code onto metered API credits (which were $0). The adapter now defaults to the
  subscription by removing that key for the call (`prefer_subscription=True`, restored after);
  `prefer_subscription=False` keeps API billing. Note 13 updated to "verified working".

## 2026-05-31 — Claude Agent SDK verified live + robust error handling

- **Verified `claude_agent_sdk_loop.py` against `claude-agent-sdk` 0.2.87**: all imported symbols match the
  real API; it compiles, authenticates via the bundled Claude Code, and registers the in-process
  `mcp__lab__calculate` tool. The machinery works end to end.
- **Observed billing block**: the model turn returned `billing_error: "Credit balance is too low"` - the
  SDK billed metered API credits, not the subscription. Documented the fix in note 13 (log in with
  `claude` so it uses subscription usage, or add API credits).
- **Hardened the adapter**: the SDK raises a confusing "error result: success" on error results; the
  adapter now catches it and surfaces the real reason (e.g. "Credit balance is too low") with guidance.

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
