---
title: "Capstone - A Production Self-Improving Agent"
tags: [self-improving-agents, curriculum, capstone, production, architecture]
module: 11
updated: 2026-06-01
---

# 11 · Capstone - A Production Self-Improving Agent

**What you'll learn** - This module wires every subsystem from the curriculum into a single, coherent, runnable agent. You will trace one complete self-improvement cycle end-to-end - from task execution through memory recording, reflection, skill proposal, evaluation gating, and conditional commit - and leave with a production checklist that keeps the system honest: budget-aware, rollback-ready, and with a human in the loop at the right moment.

> [!info] Prerequisites
> This module assumes you have completed all prior modules. The most critical is [[10 - Evaluation Harness]], which provides the external ground truth that gates every learning step. Full cross-references: [[03 - The Minimal Agent Loop]], [[04 - Memory Systems]], [[05 - Reflection and Self-Correction]], [[06 - Skill Acquisition and Curation]], [[07 - Verification Gates and Layered Control]], [[08 - Self-Modification - The DGM Pattern]], [[09 - Sandboxing and Safe Execution]], [[10 - Evaluation Harness]].

---

## Learning Objectives

- [ ] Describe the full architecture: how all seven subsystems connect in a single data flow
- [ ] Run one complete improvement cycle on both `AGENT_BACKEND=omlx` and `AGENT_BACKEND=vibeproxy`
- [ ] Apply the production checklist - skeptic's 4 questions, human-in-the-loop placement, rate-limit budget, rollback strategy
- [ ] Interpret `CHANGELOG.md` and eval trend output to tell whether the agent has actually improved
- [ ] Explain where deterministic L2 scripts are mandatory and why prompt-only control fails in production

---

## 1 - The Full Architecture

Before running anything, draw the wiring in your head. Seven subsystems, one loop.

```mermaid
%%{init: {"theme":"neutral","themeVariables":{"fontSize":"16px"},"flowchart":{"htmlLabels":true,"nodeSpacing":38,"rankSpacing":44,"padding":6,"useMaxWidth":true}}}%%
flowchart TD
    A([START - scripts/go]) --> B[agent/loop.py<br/>Baseline ACT loop]
    B --> C{Task outcome}
    C -->|success or failure| D[memory/store.py<br/>RECORD trajectory]
    D --> E[reflection/reflect.py<br/>REFLECT - extract heuristics]
    E --> F{Proposal type?}
    F -->|New skill| G[skills/library.py<br/>Write to skills/SKILLS/]
    F -->|Prompt mutation| H[evolve/loop.py<br/>Write candidate to evolve/archive/]
    F -->|No change| Z([END - no-op cycle])
    G --> I[evals/run.py<br/>VERIFY on eval suite]
    H --> I
    I --> J{eval delta >= threshold?}
    J -->|Yes - improvement confirmed| K[scripts/commit<br/>Append CHANGELOG.md<br/>git commit]
    J -->|No - regression or neutral| L[Discard candidate<br/>Log to evolve/archive/rejected/]
    K --> M([NEXT CYCLE])
    L --> M

    style A fill:#2d6a4f,color:#fff
    style K fill:#2d6a4f,color:#fff
    style L fill:#b5200d,color:#fff
    style Z fill:#555,color:#fff
    style I fill:#1d3557,color:#fff
    style J fill:#1d3557,color:#fff
```

*Full architecture: every subsystem from the curriculum connected in one deterministic flow. The VERIFY gate at `evals/run.py` is the single decision point - nothing reaches `scripts/commit` without passing it.*

The key design principle is that **only `evals/run.py` decides whether a change is kept**. Reflection and proposal are generative and fallible; the eval gate is deterministic and external. This mirrors the curriculum's thesis: for local/subscription builders, memory + skill accumulation gated by strong VERIFY is the pragmatic sweet spot over unconstrained self-modification - see [henrypan's 1k harness experiments](https://www.henrypan.com/blog/2026-05-25-self-improvement-harness/).

---

## 2 - One Complete Self-Improvement Cycle

The sequence diagram below shows the message flow across subsystems for a single cycle that ends in a committed improvement.

```mermaid
%%{init: {"theme":"neutral","themeVariables":{"fontSize":"16px"},"sequence":{"useMaxWidth":true,"wrap":true}}}%%
sequenceDiagram
    participant S as scripts/go
    participant L as agent/loop.py
    participant M as memory/store.py
    participant R as reflection/reflect.py
    participant SK as skills/library.py
    participant EV as evals/run.py
    participant C as scripts/commit

    S->>L: launch with GOAL.md + AGENTS.md context
    L->>L: ACT - execute task with tools
    L->>M: RECORD full trajectory (steps, tool calls, outcome)
    M-->>L: trajectory_id confirmed
    L->>R: REFLECT - pass trajectory + current heuristics
    R->>R: LLM critique pass (what failed, what worked)
    R-->>L: proposed_skill or proposed_mutation + rationale
    L->>SK: write candidate skill to skills/SKILLS/candidate_<hash>.py
    SK-->>L: candidate path confirmed
    L->>EV: run eval suite with candidate active
    EV->>EV: execute evals/tasks.py against both baseline and candidate
    EV-->>L: delta score (+0.04 pass-rate improvement)
    L->>L: delta >= evolve_min_delta? (yes)
    L->>SK: promote candidate to skills/SKILLS/<name>.py
    L->>C: scripts/commit "skill: add <name> (+4pp on eval suite)"
    C->>C: append CHANGELOG.md entry
    C->>C: git commit -m "..."
    C-->>S: cycle complete - improvement committed
```

*One complete improvement cycle. The LLM contributes to ACT, REFLECT, and skill authoring; deterministic scripts handle RECORD, VERIFY, and COMMIT. Nothing is entrusted to the LLM that requires guaranteed correctness.*

### What each file actually does in this cycle

| Path | Role | Subsystem |
|---|---|---|
| `scripts/go` | Launches the cycle with correct env; enforces iteration protocol | L2 deterministic |
| `agent/loop.py` | Orchestrates ACT phase; calls tools; collects outcome | Module 03 |
| `memory/store.py` | Persists trajectory to SQLite/vector store; embeddings via oMLX | Module 04 |
| `reflection/reflect.py` | LLM critique pass; returns structured proposal JSON | Module 05 |
| `skills/library.py` | Reads/writes the skill library; manages candidate lifecycle | Module 06 |
| `evolve/loop.py` | Handles prompt/code mutation proposals; writes to `evolve/archive/` | Module 08 |
| `evals/run.py` | Runs eval suite; returns delta score vs. baseline | Module 10 |
| `verification/gates.py` | Contains threshold constants + gate logic (imported by evals/run.py) | Module 07 |
| `scripts/commit` | Safe commit wrapper; appends CHANGELOG.md atomically | L2 deterministic |

> [!note] L2 Scripts are Non-Negotiable
> The production finding from [NousResearch hermes-agent issue #29652](https://github.com/NousResearch/hermes-agent/issues/29652) is explicit: "Layer 1 (Prompt) alone failed - agents skipped explicit instructions." In this scaffold, `scripts/go` and `scripts/commit` are L2 deterministic scripts. They cannot be overridden by a model's reasoning. RECORD, VERIFY threshold checking, and git commit are always L2. Only ACT and REFLECT are LLM-driven.

---

## 3 - Hands-On Lab: Running the Full Cycle

### 3.1 - Environment setup

```bash
cd /Users/yuxinliu/self-improving-agent-lab
cp .env.example .env
# Edit .env and set at minimum:
#   AGENT_BACKEND=omlx        # or vibeproxy
#   OMLX_MODEL=qwen2.5-coder-7b
#   VIBE_MODEL=claude-sonnet-4-5-20250929
#   EVOLVE_MIN_DELTA=0.05     # min eval delta to accept a change
#   HUMAN_IN_LOOP=true        # pause before committing
pip install -r requirements.txt
```

Both backends use the same adapter from `backends/adapter.py`:

```python
# backends/adapter.py - canonical adapter (do not modify)
import os
from openai import OpenAI

BACKENDS = {
    "omlx":      {"base_url": "http://localhost:8000/v1",  "model": os.getenv("OMLX_MODEL", "qwen2.5-coder-7b")},
    "vibeproxy": {"base_url": "http://localhost:8317/v1",  "model": os.getenv("VIBE_MODEL",  "claude-sonnet-4-5-20250929")},
}

def make_client(backend=None):
    b = BACKENDS[backend or os.getenv("AGENT_BACKEND", "omlx")]
    return OpenAI(base_url=b["base_url"], api_key=os.getenv("LLM_API_KEY", "not-needed")), b["model"]
```

> [!warning] VibeProxy embeddings caveat
> VibeProxy exposes chat only - there is NO embeddings endpoint on the Claude subscription. The memory layer always uses oMLX's local embeddings endpoint (`http://localhost:8000/v1`) regardless of which backend handles generation. If oMLX is not running when you use `AGENT_BACKEND=vibeproxy`, `memory/store.py` will raise a connection error. Start oMLX first, even in vibeproxy mode.

### 3.2 - Running one cycle (omlx)

```bash
# Ensure oMLX is running (menu-bar icon, model loaded)
AGENT_BACKEND=omlx scripts/go
```

The `scripts/go` iteration protocol (from [agent-seed](https://github.com/B67687/agentic-workflows/pull/82)):

```bash
#!/usr/bin/env bash
# scripts/go
set -euo pipefail

BACKEND="${AGENT_BACKEND:-omlx}"
echo "=== Cycle start: backend=$BACKEND $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a CHANGELOG.md

python -m agent.loop \
  --goal GOAL.md \
  --agents AGENTS.md \
  --backend "$BACKEND" \
  --record-to memory/store.py \
  --reflect-with reflection/reflect.py \
  --verify-with evals/run.py \
  --threshold "${EVOLVE_MIN_DELTA:-0.05}" \
  --human-in-loop "${HUMAN_IN_LOOP:-true}"

echo "=== Cycle end: $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a CHANGELOG.md
```

### 3.3 - Running one cycle (vibeproxy)

```bash
# VibeProxy must be running (menu-bar icon, Claude MAX session active)
# oMLX must ALSO be running for embeddings
AGENT_BACKEND=vibeproxy scripts/go
```

The adapter swaps `base_url` automatically. No other change is needed. The generation calls go to `http://localhost:8317/v1`; embedding calls inside `memory/store.py` always go to `http://localhost:8000/v1`.

> [!tip] ToS reminder
> Using a Claude MAX subscription via VibeProxy routes your OAuth session through a local proxy. This may violate Anthropic's Terms of Service. Evaluate your own risk tolerance before use.

### 3.4 - The core orchestration: the improvement cycle

This is the integration point that wires the subsystems together. It is the distilled logic of `scripts/go` (the real driver) - and unlike a sketch, **every import and call below resolves against the scaffold's actual API**. Note the shape: the scaffold is *functional* (`propose_skill()`, `save_skill()`, `run_evals()`), and `verify()` is a pure gate you feed scores into - it decides keep/discard, it does not compute the scores itself.

```python
# The end-to-end ACT -> RECORD -> REFLECT -> LEARN -> VERIFY -> COMMIT cycle,
# distilled from scripts/go. Run it with `./scripts/go`.
from agent.loop import run_agent
from memory.store import MemoryStore
from reflection.reflect import reflect_on_trajectory
from skills.library import propose_skill, save_skill, list_skills
from evals.run import run_evals
from verification.gates import verify, VerdictStatus


def run_improvement_cycle(task: str, backend: str | None = None) -> dict:
    memory = MemoryStore()                       # SQLite + oMLX embeddings

    # --- ACT (past lessons are injected into the prompt via memory=) ---
    result = run_agent(task, backend=backend, memory=memory, log=True)
    print(f"[ACT] success={result.success} stop={result.stop_reason} rounds={result.rounds_used}")

    # --- RECORD (persist the trajectory shape for replay/audit) ---
    memory.record_trajectory({
        "task": result.task, "answer": result.answer,
        "success": result.success, "steps": len(result.trajectory),
    })
    print(f"[RECORD] trajectory of {len(result.trajectory)} steps stored")

    # --- REFLECT (structured lessons -> memory; the read side of the NEXT act) ---
    lessons = reflect_on_trajectory(result, store=memory)
    print(f"[REFLECT] heuristic={lessons.heuristic[:60]!r} conf={lessons.confidence}")

    # --- LEARN (propose a reusable skill from the trajectory) ---
    summary = f"Task: {result.task}\nAnswer: {result.answer}"
    skill = propose_skill(summary, source_task=task)
    if skill is None:
        return {"committed": False, "reason": "no skill proposed"}
    print(f"[LEARN] candidate skill {skill.name!r}")

    # --- VERIFY (min_delta defaults to settings.evolve_min_delta; the always-on
    #     containment gate from section 4.4 runs UNCONDITIONALLY; run_safety_check
    #     defaults True so the LLM safety gate also runs) ---
    baseline = run_evals(backend=backend).score
    candidate = baseline + (0.1 if result.success else 0.0)   # prod re-scores the suite with the candidate applied
    verdict = verify(
        proposal={"type": "skill", "name": skill.name, "content": skill.description},
        candidate_score=candidate,
        baseline_score=baseline,
    )
    print(f"[VERIFY] {verdict.status.value.upper()} (delta={verdict.delta:+.4f}) - {verdict.reason}")

    if verdict.status is not VerdictStatus.ACCEPT:
        return {"committed": False, "delta": verdict.delta, "reason": verdict.reason}

    # --- COMMIT (persist the skill; scripts/commit wraps git so it stays revertible) ---
    skill.eval_score = verdict.score
    path = save_skill(skill)
    print(f"[COMMIT] saved {skill.name!r} -> {path.name}; library now {list_skills()}")
    return {"committed": True, "delta": verdict.delta, "skill": skill.name}
```

### 3.5 - Human-in-the-loop gate

The `HUMAN_IN_LOOP=true` flag inserts a confirmation step before `scripts/commit` runs. This is the single intervention that [community consensus](https://www.reddit.com/r/AI_Agents/comments/1taei9m/stop_building_ai_agents/) identifies as saving "90% of the headache."

```python
# In run_improvement_cycle, immediately before the COMMIT block:
import os
if os.getenv("HUMAN_IN_LOOP", "true").lower() == "true":
    print(f"\n[HUMAN-IN-LOOP] skill={skill.name!r}  delta={verdict.delta:+.4f}")
    print(f"Steps preview: {skill.steps[:3]}")
    if input("Accept and commit? [y/N] ").strip().lower() != "y":
        return {"committed": False, "reason": "human rejected"}
```

---

## 4 - Production Checklist

This checklist is the skeptic's 4-question framework applied to self-improving agents, extended with operational concerns.

### 4.0 - Harness Completeness Checklist

Per the brain/harness/agent framing in [[00 - Curriculum Map]], a production harness is ~10 distinct subsystems. This table is the audit: which does this lab implement, which does it teach, and which are deliberately out of scope for a single-operator learning scaffold. Use it to know exactly what you would still need before shipping an agent to a business - and what to rent from a platform rather than hand-roll (see [[13 - Graduating to a Framework]]).

| # | Harness subsystem | Lab status | Where |
|---|---|---|---|
| 1 | Model client (retry/backoff, timeout, cost accounting) | Partial | `backends/adapter.py` - retry/timeout taught in [[02 - Backends - oMLX and VibeProxy]] |
| 2 | Model routing (light for intent, strong for reasoning) | Partial | `backends/router.py` - `route()`/`RouteDecision`, wired at 4 callsites |
| 3 | Context assembly + compression (per-request budget, not whole-project dump) | Partial | `agent/loop.py` `_build_system_prompt` + memory retrieval; see [[03 - The Minimal Agent Loop]], [[04 - Memory Systems]] |
| 4 | Tool system (define, dispatch, fail-as-observation) | Full | `agent/tools.py` `TOOL_SCHEMAS`/`dispatch_tool` |
| 5 | Structured edit / diff-apply with rollback | Implemented | `agent/tools.py` `edit_file` - anchored old→new edit, unique-anchor validation, atomic write, snapshot for rollback; see [[09 - Sandboxing and Safe Execution]] §4.1 |
| 6 | Execution environment / sandbox isolation | Partial (taught, worktree-runner build) | [[09 - Sandboxing and Safe Execution]] |
| 7 | State, memory, checkpoint/rollback | Full (memory) / Partial (checkpoint) | `memory/store.py`; `scripts/commit`; [[04 - Memory Systems]], [[08 - Self-Modification - The DGM Pattern]] |
| 8 | Scheduling loop (continue / stop / when-to-reflect) | Full (continue-stop) / Partial (adaptive reflect) | `agent/loop.py`, `scripts/go` |
| 9 | Identity + permissions (capability scoping; caller-principal) | Partial (capability scoping) / Out-of-scope (multi-tenant) | `verification/gates.py`, `agent/tools.py` write-allowlist; multi-user is a production concern the lab omits |
| 10 | Observability (log-every-step, replay, debug) | Implemented | `agent/runlog.py` append-only JSONL per-step log (token telemetry) + `agent/replay.py` time-travel trace |
| 11 | Security (block dangerous ops, prompt-injection defense) | Implemented | `verification/gates.py` `requires_sandbox`/`_gate_containment` (always-on escalation) + `agent/quarantine.py` (injection framing) + `agent/net_guard.py` (egress allowlist); `SAFE-001` eval; see §4.4 |
| 12 | API layer + deployment | Out-of-scope | CLI/library only; intentionally omitted for a local learning scaffold |

"GAP - exercise" and "Out-of-scope" are honest labels, not apologies: the lab's job is to teach each primitive well enough that you recognize a production-grade implementation when you rent one. Items 9 (multi-tenant), 12 (deploy), and concurrent tool execution are general-production-harness concerns - acknowledge them, then reach for a platform.

### 4.1 - The skeptic's 4 questions (apply before each feature)

Drawn from [community hard-won experience](https://www.reddit.com/r/AI_Agents/comments/1taei9m/stop_building_ai_agents/):

| Question | If yes | If no |
|---|---|---|
| Can you draw the flow as clear, enumerable steps? | Make it a deterministic script (L2). Skip the LLM. | Agent may be appropriate |
| Does this path have >5 branches with unpredictable inputs? | Consider an agent for that path only | Automation is fine |
| Is the worst-case wrong answer high-cost? | Automation only, or HITL on every execution | Agent with VERIFY gate |
| Will compliance review this? | Automation, full stop - no agent | Proceed with caution |

> [!danger] Never self-approve
> The [NousResearch production finding](https://github.com/NousResearch/hermes-agent/issues/29652) is a hard rule: the agent must not evaluate its own proposals. `evals/run.py` is an external, deterministic judge. The agent's LLM does not see the eval results before they are computed - it only sees the final keep/discard decision.

### 4.2 - Rate-limit budget

These backends are rate-limited, not per-token-metered. A naive reflection loop can exhaust limits without spending money. Design for throughput, not cost.

```python
# config.py - rate limit budget for one cycle
RATE_LIMIT_CONFIG = {
    "max_act_calls":      10,   # tool calls during ACT phase
    "max_reflect_calls":   3,   # LLM calls during REFLECT
    "max_eval_tasks":     20,   # eval tasks per VERIFY run
    "min_seconds_between_cycles": 30,  # hard floor to avoid hammering the proxy
}
```

> [!tip] Model routing within a cycle
> For cheap steps (RECORD formatting, candidate file naming, changelog entry), use a small oMLX model. Reserve the larger model (Claude via vibeproxy, or a 32B oMLX model) for REFLECT and skill authoring. The [community consensus](https://www.reddit.com/r/AI_Agents/comments/1taei9m/stop_building_ai_agents/) is explicit: "don't default to flagship for every call." `backends/router.py` handles this - assign model tiers per phase.

### 4.3 - Rollback strategy

Every committed change is a git commit. Rolling back is a git operation, not a special agent function.

```bash
# See what changed in the last 5 improvement cycles
git log --oneline -10

# Roll back to a known-good state (e.g., before last 3 skill commits)
git revert HEAD~3..HEAD --no-commit
git commit -m "chore: revert last 3 skill additions (eval regression)"

# Or, to inspect the eval trend before deciding:
python evals/run.py --trend --last-n 10
```

The `CHANGELOG.md` is append-only and committed with every skill. It is the human-readable audit trail. The eval trend from `evals/run.py --trend` is the numeric audit trail.

> [!info] Three audit layers, not one
> These two are *summary* trails - they tell you a change happened and whether the score moved. They do NOT let you reconstruct *what the agent actually did* inside a run. That is the third layer: the **per-step run log**. With `run_agent(..., log=True)` (on by default in `scripts/go`), `agent/runlog.py` writes an append-only `logs/run-<ts>-<id>.jsonl` - one record per step (`run_start`, each tool call + args, `run_end` with success/stop-reason/token-total). The CHANGELOG answers "did it improve?"; the run log answers "*why* - which step, which tool, which observation - did this run behave the way it did?" It is also the substrate `agent/replay.py` reads to step through a recorded trajectory deterministically.

### Resilience: a transient blip must not end a cycle

These backends are *rate-limited*, so 429s are expected, and a large local model can hang. `backends/adapter.py` wraps every model call in `_with_retry` - capped exponential backoff for the **retryable** class (429, 5xx, timeout, connection drop) and immediate raise for the **fatal** class (auth, bad-request), because retrying a 400 only burns rate-limit headroom. A per-request `LLM_TIMEOUT_S` (default 60) stops a hung model from blocking forever. This retryable-vs-fatal taxonomy is the load-bearing distinction: see [[02 - Backends - oMLX and VibeProxy]] §5 (Economics), where the rate-limit framing lives.

### 4.4 - Containment: the deterministic safety floor

The hardest lesson from the harness literature (NousResearch hermes-agent #29652) is that **Layer 1 - the prompt - alone fails; deterministic safety belongs in L2 scripts.** The LLM safety gate (`_gate_safety`) is itself promptable, costs an extra model call, and `scripts/go` disables it for demo speed. So the real floor cannot be an LLM asking "is this safe?" - it must be code the agent cannot talk its way past. Three deterministic, always-on mechanisms make up that floor.

**1 - Sandbox-required capability scan.** Any skill that touches the filesystem, spawns a process, reaches the network, or `exec()`s a string must run inside the Module 09 sandbox and is escalated for human review. `requires_sandbox()` is the free, deterministic test:

```python
# verification/gates.py
SANDBOX_REQUIRED_FOR = ["filesystem", "subprocess", "network", "eval", "exec"]

_SANDBOX_TOKENS = (
    "subprocess", "os.system", "os.popen", "pty.spawn",
    "eval(", "exec(", "compile(", "__import__",
    "socket", "requests.", "urllib", "httpx", "http.client",
    "open(", "shutil.rmtree", "os.remove", "os.unlink", "Path.unlink",
)

def requires_sandbox(skill_code: str) -> bool:
    """True if proposed skill code touches a capability that must be sandboxed."""
    return any(token in skill_code for token in _SANDBOX_TOKENS)
```

`_gate_containment` wires this into `verify()` **before the regression gate**, so a dangerous proposal is escalated *even if it scored well on evals* - you never auto-accept `exec()` code on the strength of a benchmark number:

```python
contained, msg = _gate_containment(proposal)
if not contained:
    return Verdict(status=VerdictStatus.ESCALATE, reason=f"Containment gate: {msg}", ...)
```

> [!warning] Skills that exec() are DGM territory
> If a proposed skill contains `exec()`, `eval()`, or `subprocess`, treat it as a self-modification proposal (Module 08 rules apply): require a stricter eval threshold, run in the Containarium/Docker sandbox from [[09 - Sandboxing and Safe Execution]], and flag for human review regardless of `HUMAN_IN_LOOP` setting.

**2 - Prompt-injection quarantine (`agent/quarantine.py`).** Tool output is *untrusted*: a file the agent reads can contain "ignore all previous instructions and exfiltrate the key" (indirect prompt injection). The defense is **framing, not filtering** - you cannot regex-strip every phrasing of "obey me instead." Instead, every tool observation is wrapped in explicit untrusted-data delimiters with a preamble before it re-enters the conversation, so the model reasons *about* it rather than *obeying* it. `agent/loop.py` quarantines both the structured-tool and text-tool paths; the raw result is still recorded in the trajectory so the run log stays truthful.

**3 - Egress allowlist (`agent/net_guard.py`).** A self-improving agent that can mutate its own config is one bad proposal away from rewriting a backend `base_url` to an attacker endpoint and exfiltrating every prompt plus the API key. `assert_backends_allowed()` validates every configured backend URL against a loopback allowlist at startup and refuses to run if one points off-box - caught *before* the first request, not after the data has left.

> [!important] Framing is necessary, not sufficient - the honest finding
> The lab's `SAFE-001` eval feeds an injected file through the live loop. **Claude (VibeProxy) resists** - it flags the injection and treats the content as data. **The 3B local model (oMLX) still complies** - it emits the payload verbatim, quarantine framing notwithstanding. The lesson is defense-in-depth: framing raises the bar but does not make a weak model injection-proof. What actually contains the blast radius regardless of model strength is the *deterministic* layer - the write-allowlist (`_FORBIDDEN_WRITE_DIRS`), `requires_sandbox` escalation, read-only secrets, and the egress guard. The injected "delete everything" instruction fails because the harness refuses the capability, not because the model resisted.

---

## 5 - Monitoring: Did It Actually Improve?

Two artifacts tell you whether the agent is improving over time: `CHANGELOG.md` and the eval trend.

### 5.1 - Reading CHANGELOG.md

```markdown
## 2026-05-31 - parse_json_safely
- delta: +0.04 on eval suite
- rationale: agent was failing on malformed JSON from tool calls; new skill wraps json.loads with recovery

## 2026-05-30 - retry_on_rate_limit
- delta: +0.02 on eval suite
- rationale: intermittent rate-limit errors caused task failures; skill adds exponential backoff

## 2026-05-29 - (no commit)
- candidate extract_table_data: delta -0.01 - discarded (below threshold)
```

A healthy CHANGELOG shows: small, positive, explained deltas; occasional discards (the VERIFY gate is working); a clear rationale that a human can audit.

An unhealthy CHANGELOG shows: large unexplained deltas; no discards ever (VERIFY gate too loose); skills with generic names and vague rationales.

### 5.2 - Eval trend output

```bash
python evals/run.py --trend --last-n 20
```

Expected output format:

```
Eval trend (last 20 cycles):
  Cycle  Score   Delta   Committed  Skill
  001    0.610   -       -          (baseline)
  002    0.634   +0.024  YES        retry_on_rate_limit
  003    0.634   +0.000  NO         (no proposal)
  004    0.638   +0.004  YES        parse_json_safely
  005    0.635   -0.003  NO         (candidate rejected)
  ...
  020    0.671   +0.061  -          (cumulative gain)

Cumulative improvement: +6.1pp over 20 cycles
Acceptance rate: 7/20 (35%)
```

> [!tip] What good numbers look like
> The [Darwin Gödel Machine](https://arxiv.org/abs/2505.22954) reports 20% to 50% gains on SWE-bench over many cycles - but that is an unconstrained self-rewriting system on a narrow benchmark. For a memory + skill system on general tasks, expect 5-15pp cumulative gain over 20-50 cycles before plateauing. An acceptance rate of 20-40% means the VERIFY gate is doing real work. 100% acceptance means `EVOLVE_MIN_DELTA` is too low. 0% means the reflection quality is poor or the tasks are too hard for the model.

### 5.3 - Diagnosing a plateau

If improvement stalls:

1. Check reflection quality - is `reflect.py` extracting specific, actionable heuristics, or generic ones? See [[05 - Reflection and Self-Correction]].
2. Check skill diversity - is the library accumulating redundant skills? Use `skills/library.py --dedupe`. See [[06 - Skill Acquisition and Curation]].
3. Check eval coverage - are the eval tasks too easy (ceiling effect) or too hard (floor effect)? See [[10 - Evaluation Harness]].
4. Check memory retrieval - is the agent retrieving relevant past trajectories, or is retrieval degrading? See [[04 - Memory Systems]].
5. Consider a harder task distribution - the agent may have exhausted the improvement surface on current tasks. Update `GOAL.md`.

---

## 6 - Pitfalls

> [!danger] Recursive drift without external evals
> If you let the agent evaluate its own proposals - even indirectly, through a "self-critic" prompt - you lose the external ground truth. The [Continual Harness paper](https://arxiv.org/abs/2605.09998) documents this as "recursive drift": the agent learns to game its own critic rather than to improve on actual tasks. The eval suite in `evals/tasks.py` must contain tasks the agent did NOT author.

> [!warning] Prompt-only control fails at scale
> Do not put safety constraints, commit guards, or threshold checks inside a system prompt and expect them to hold. The [hermes-agent production finding](https://github.com/NousResearch/hermes-agent/issues/29652) is the canonical reference: L1 (prompt) constraints were bypassed; L2 (scripts) held. Every hard constraint in this scaffold is in `scripts/go`, `scripts/commit`, and `verification/gates.py` - not in a prompt.

> [!warning] Embeddings break silently on vibeproxy-only setups
> If oMLX is not running and `AGENT_BACKEND=vibeproxy`, the memory store will silently fall back to no-op or crash depending on error handling. Always verify oMLX is serving on `:8000` before running any cycle. The architecture requires local embeddings regardless of generation backend.

> [!tip] The "3am Slack message" rule
> From [community experience](https://www.reddit.com/r/AI_Agents/comments/1taei9m/stop_building_ai_agents/): "3am Slack message when the agent approves the wrong invoices." For a self-improving agent, the equivalent is an unreviewed skill commit that degrades production behavior. `HUMAN_IN_LOOP=true` is the default for this reason. Disable it only for tasks where the worst-case wrong answer is reversible and cheap.

> [!danger] Skills accumulate technical debt
> The [SkillOS paper](https://arxiv.org/abs/2605.06614) and [Muse-Autoskill](https://arxiv.org/abs/2605.27366) both document skill proliferation as a failure mode: the library grows, retrieval degrades, and new skills conflict with old ones. Run `skills/library.py --audit` periodically to prune skills that have not been invoked in N cycles. A skill that is never retrieved is a liability, not an asset.

> [!note] Self-modification is a separate regime
> This capstone defaults to skill accumulation (camp 2 in the curriculum's taxonomy). If you want to explore prompt mutation or code rewriting (camp 1, Module 08), keep those candidates in `evolve/archive/` with a stricter `EVOLVE_MIN_DELTA` (e.g., 0.10 rather than the 0.05 default) and always sandbox execution. The [DGM paper](https://arxiv.org/abs/2505.22954) documents what full self-rewriting can achieve, but it requires a narrow, benchmarkable problem and a hermetic sandbox.

---

> [!question] Checkpoint
> 1. In the full architecture diagram, what is the only decision point that can route a proposal to `scripts/commit`? Why must this step be deterministic rather than LLM-driven?
> 2. Why does `memory/store.py` always connect to `http://localhost:8000/v1` for embeddings, even when `AGENT_BACKEND=vibeproxy`?
> 3. You observe that the acceptance rate in your eval trend is 95% over 30 cycles. What does this suggest about your `EVOLVE_MIN_DELTA`, and what risk does it create?
> 4. A proposed skill contains `subprocess.run(...)`. According to `verification/gates.py`, what additional requirements must be satisfied before this skill can be committed?
> 5. Your CHANGELOG shows three consecutive cycles with `delta: +0.08` for skills with names like `general_improvement_v1`, `general_improvement_v2`. What two failure modes does this pattern signal?

> [!tip] Next step
> Once your capstone runs end to end, see [[13 - Graduating to a Framework]] for when to swap a hand-built piece for mem0 or Pydantic AI - without changing your backends.

---

## Navigation

← [[10 - Evaluation Harness]] · [[00 - Curriculum Map]] (home) · [[12 - Resources and Field Map]] → · [[14 - Framework Capstone - Shipping on deepagents]] (the buy counterpart)
