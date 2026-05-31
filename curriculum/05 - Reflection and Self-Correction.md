---
title: "Reflection and Self-Correction"
tags: [self-improving-agents, curriculum, reflection, self-correction, metacognition]
module: 05
updated: 2026-05-31
---

# 05 · Reflection and Self-Correction

**What you'll learn** - This module covers the REFLECT step of the ACT -> RECORD -> REFLECT -> LEARN loop. You will learn how to critique a recorded trajectory, extract reusable heuristics from that critique, distinguish between in-task self-correction (retry within a single run) and cross-task reflection (lessons that persist to future runs), and understand why reflection without external anchors causes recursive drift - a failure mode that makes agents progressively worse.

> [!info] Prerequisites
> - [[04 - Memory Systems]] - trajectory recording and memory primitives the REFLECT step reads from
> - Familiarity with the canonical loop vocabulary (ACT / RECORD / REFLECT / LEARN / VERIFY)

## Learning Objectives

- [ ] Explain what a "trajectory critique" is and write a self-critique prompt over a recorded trajectory
- [ ] Implement `reflection/reflect.py` to produce structured lessons from a (trajectory, outcome) pair
- [ ] Distinguish in-task self-correction from cross-task reflection and know when each applies
- [ ] Describe [Experiential Reflective Learning (ERL)](https://arxiv.org/pdf/2603.24639) and what "experiential" means relative to pure in-context critique
- [ ] State the recursive drift failure mode and name the two modules that provide the external anchors needed to prevent it
- [ ] Configure the multi-agent critique pattern to cross-validate lessons before they enter memory

---

## 1. What Is Reflection?

After every task run the agent has two artifacts: the **trajectory** (the full sequence of thoughts, tool calls, and outputs captured in Module 04) and the **outcome** (pass / fail / partial, plus any ground-truth signal). Reflection is the process of comparing those two artifacts and producing structured, reusable knowledge.

The word "reflection" is overloaded. In this curriculum it always means the REFLECT step of the canonical loop - a deliberate, LLM-driven critique pass that happens *after* the run ends, writes structured lessons to memory, and feeds into the LEARN step (Modules 06 and 08). It is not in-context chain-of-thought reasoning that occurs *during* a run (that is covered under in-task self-correction in Section 3).

[Experiential Reflective Learning (ERL)](https://arxiv.org/pdf/2603.24639) formalizes this distinction: "experiential" means the agent accumulates lessons *across* experiences rather than just reasoning within one context window. The key insight is that the lesson store outlives any single run - it is persistent memory, not just a longer prompt.

---

## 2. The REFLECT Pipeline

```mermaid
%%{init: {"theme":"neutral","themeVariables":{"fontSize":"16px"},"flowchart":{"htmlLabels":true,"nodeSpacing":38,"rankSpacing":44,"padding":6,"useMaxWidth":true}}}%%
flowchart TD
    T["Trajectory<br/>(tool calls, outputs, reasoning)"]
    O["Outcome<br/>(pass/fail, ground truth, human score)"]
    C["Critique LLM call<br/>(self-critique prompt)"]
    S["Structured Lessons<br/>(heuristics + failure modes)"]
    F["Filter<br/>(multi-agent cross-check)"]
    M["Memory / Lesson Store<br/>(vector + structured)"]

    T --> C
    O --> C
    C --> S
    S --> F
    F -->|"accepted"| M
    F -->|"rejected"| discard["Discarded<br/>(low confidence)"]
```

*The REFLECT pipeline: trajectory and outcome feed a critique call, which produces structured lessons, which are filtered by multi-agent cross-check before writing to memory.*

Key design choices visible in the diagram:

- **Two inputs are required.** Trajectory alone is insufficient - without the outcome you cannot know whether the reasoning was sound or merely fluent. This is why RECORD (Module 04) must capture outcome signals, not just the chain-of-thought.
- **Filter before write.** Raw LLM self-critique is noisy. The multi-agent cross-check (Section 5) reduces false positives in the lesson store.
- **Memory is the output.** Lessons that do not reach the store produce no durable improvement.

---

## 3. In-Task Self-Correction vs. Cross-Task Reflection

These two mechanisms are often conflated. They operate at different scopes and have different failure modes.

| Dimension | In-task self-correction | Cross-task reflection |
|---|---|---|
| Scope | Single run, current context window | Across runs, persistent memory |
| Trigger | Tool call fails, assertion fails, own check | Run ends with an outcome signal |
| Output | Revised action in the same run | Structured lesson written to store |
| Persistence | None - lost when context ends | Durable - available to future runs |
| Risk | Infinite retry loops without a budget | Recursive drift if unchecked |

### 3a. In-Task Self-Correction

The agent attempts an action, checks the result, and revises before moving on. This is useful and cheap - no memory write required. The danger is unconstrained retries.

```mermaid
%%{init: {"theme":"neutral","themeVariables":{"fontSize":"16px"}}}%%
stateDiagram-v2
    [*] --> Attempt
    Attempt --> Check : result received
    Check --> Revise : check fails<br/>(retries < budget)
    Revise --> Attempt : retry
    Check --> Done : check passes
    Check --> GiveUp : retries >= budget
    Done --> [*]
    GiveUp --> [*]
```

*In-task self-correction state machine: Attempt -> Check -> Revise loops back until success, budget exhaustion, or a passing check.*

The budget is critical. Without it, a stubborn wrong assumption loops forever. In `agent/loop.py` this is the `max_retries` guard. When the budget is exhausted the run terminates with a failure outcome, which then feeds the cross-task reflection path.

### 3b. Cross-Task Reflection

This is the REFLECT step proper. It runs *after* the run terminates and produces lessons that survive into future runs. Because it writes to shared memory, it has a much higher impact - and a correspondingly higher risk if the lessons are wrong.

> [!warning] Recursive Drift
> Self-feedback alone - an agent critiquing its own trajectories without any external anchor - causes **recursive drift**: the agent's lessons increasingly reflect its own biases and blind spots rather than ground truth. Early lessons look plausible. Later lessons are confidently wrong. The agent becomes better at being wrong.
>
> Prevention requires external anchoring at every LEARN step:
> - **Module 07** [[07 - Verification Gates and Layered Control]] - deterministic test gates that reject code changes before they commit
> - **Module 10** [[10 - Evaluation Harness]] - benchmark suites that catch performance regression over time
>
> Never let a reflection run write to memory without at least one of these signals present.

---

## 4. The Self-Critique Prompt

The critique prompt is the core of the REFLECT step. It takes the trajectory and outcome as context and asks the LLM to reason about what went wrong, what went right, and what rule would have produced a better result.

A good critique prompt has three parts:

1. **Grounding** - present the trajectory and outcome verbatim so the model does not hallucinate what happened
2. **Structured output** - request JSON with explicit fields for heuristics and failure modes, not free prose
3. **Confidence gate** - ask the model to score its own confidence; lessons below a threshold are discarded before the filter step

Example prompt template (used in `reflection/reflect.py`):

```
You are a trajectory analyst. You will receive a complete agent trajectory and its outcome.
Produce a JSON object with these fields:
  - summary: one sentence describing what the agent tried to do
  - failure_mode: null if success, otherwise a specific description of what went wrong
  - heuristics: list of up to 3 short rules the agent should follow in future similar tasks
  - anti_patterns: list of up to 2 things the agent did that made the outcome worse
  - confidence: float 0-1, your confidence that these lessons generalize beyond this single run

Trajectory:
{trajectory}

Outcome:
{outcome}
```

The `confidence` field is the self-filter. Lessons with confidence below 0.6 are discarded. This is not sufficient on its own (see Section 5) but it reduces noise.

---

## 5. Multi-Agent Critique

Single-agent self-critique has a systematic bias: the same model that made the mistakes is judging them. [The metacognitive position paper](https://openreview.net/forum?id=4KhDd0Ozqe) argues that genuine self-improvement requires decoupling the actor from the evaluator.

A practical production pattern is to run the critique with a *second* model invocation (or a second agent role) and require agreement before writing to memory. HN discussion of production multi-agent critique systems describes the dynamic informally: "agents bully each other to prevent context drift" - meaning when two independent critiques disagree, neither is written, forcing a conservative default.

Implementation options in order of cost:

1. **Same model, different system prompt** - least expensive, moderate independence
2. **Different model via router** - e.g., oMLX small model for first pass, VibeProxy Claude for second pass
3. **Separate agent process** - highest independence, highest overhead

For the lab in this module, option 1 is used. Option 2 is the production recommendation and is shown in `backends/router.py`.

---

## 6. Hands-On Lab - `reflection/reflect.py`

**Goal** - Given a trajectory dict and an outcome string, produce structured lessons and write them to the memory store.

**Scaffold file** - `reflection/reflect.py`

The lab builds on `memory/store.py` (Module 04) and `backends/adapter.py`.

### Step 1 - Set up your environment

```bash
cd /Users/yuxinliu/self-improving-agent-lab
source .venv/bin/activate
cp .env.example .env
# Set AGENT_BACKEND=omlx or AGENT_BACKEND=vibeproxy in .env
```

### Step 2 - Implement `reflection/reflect.py`

```python
# reflection/reflect.py
"""
REFLECT step: critique a trajectory + outcome, extract structured lessons,
write accepted lessons to the memory store.

Works on both backends:
  AGENT_BACKEND=omlx       -> http://localhost:8000/v1
  AGENT_BACKEND=vibeproxy  -> http://localhost:8317/v1

Note: embeddings for the lesson store always use oMLX regardless of AGENT_BACKEND,
because VibeProxy (Claude subscription) does not expose an embeddings endpoint.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from typing import Optional

from openai import OpenAI

# --- unified adapter (see backends/adapter.py) ---
BACKENDS = {
    "omlx":      {"base_url": "http://localhost:8000/v1",  "model": os.getenv("OMLX_MODEL", "qwen2.5-coder-7b")},
    "vibeproxy": {"base_url": "http://localhost:8317/v1",  "model": os.getenv("VIBE_MODEL", "claude-sonnet-4-5-20250929")},
}

def make_client(backend: Optional[str] = None) -> tuple[OpenAI, str]:
    b = BACKENDS[backend or os.getenv("AGENT_BACKEND", "omlx")]
    return OpenAI(base_url=b["base_url"], api_key=os.getenv("LLM_API_KEY", "not-needed")), b["model"]

# --- embeddings always local via oMLX ---
def _embed(text: str) -> list[float]:
    emb = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")
    return emb.embeddings.create(model="nomic-embed-text", input=text).data[0].embedding

# --- data model ---
@dataclass
class Lesson:
    summary: str
    failure_mode: Optional[str]
    heuristics: list[str]
    anti_patterns: list[str]
    confidence: float
    source_trajectory_id: str

CRITIQUE_SYSTEM = """You are a trajectory analyst for a self-improving AI agent.
Analyse the trajectory and outcome provided. Respond ONLY with valid JSON matching
this exact schema (no markdown fences, no extra keys):
{
  "summary": "<one sentence>",
  "failure_mode": "<specific description or null>",
  "heuristics": ["<rule>", ...],
  "anti_patterns": ["<anti-pattern>", ...],
  "confidence": <float 0.0-1.0>
}
Heuristics must be specific and actionable, not generic advice.
Confidence should be LOW (< 0.5) if the outcome is ambiguous or the trajectory is short."""

CRITIQUE_USER = """Trajectory (JSON):
{trajectory}

Outcome:
{outcome}"""

def critique(
    trajectory: dict,
    outcome: str,
    trajectory_id: str,
    confidence_threshold: float = 0.6,
    backend: Optional[str] = None,
) -> Optional[Lesson]:
    """
    Run a single self-critique pass. Returns a Lesson if confidence >= threshold,
    else returns None (lesson discarded).
    """
    client, model = make_client(backend)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": CRITIQUE_SYSTEM},
            {"role": "user",   "content": CRITIQUE_USER.format(
                trajectory=json.dumps(trajectory, indent=2),
                outcome=outcome,
            )},
        ],
        temperature=0.2,  # low temperature for consistent structured output
    )

    raw = response.choices[0].message.content.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"[reflect] JSON parse error: {exc}\nRaw output:\n{raw}")
        return None

    lesson = Lesson(
        summary=data.get("summary", ""),
        failure_mode=data.get("failure_mode"),
        heuristics=data.get("heuristics", []),
        anti_patterns=data.get("anti_patterns", []),
        confidence=float(data.get("confidence", 0.0)),
        source_trajectory_id=trajectory_id,
    )

    if lesson.confidence < confidence_threshold:
        print(f"[reflect] Lesson discarded (confidence={lesson.confidence:.2f} < {confidence_threshold})")
        return None

    return lesson


def cross_critique(
    trajectory: dict,
    outcome: str,
    trajectory_id: str,
    confidence_threshold: float = 0.6,
) -> Optional[Lesson]:
    """
    Multi-agent cross-critique: run two independent critique passes.
    Accept only if BOTH passes return a lesson AND their heuristic sets overlap.
    This implements the 'agents bully each other' pattern to reduce drift.

    Pass 1: primary backend (AGENT_BACKEND env var)
    Pass 2: omlx (always local, independent temperature seed)
    """
    lesson_a = critique(trajectory, outcome, trajectory_id, confidence_threshold)
    lesson_b = critique(trajectory, outcome, trajectory_id, confidence_threshold, backend="omlx")

    if lesson_a is None or lesson_b is None:
        print("[reflect] Cross-critique: one pass returned no lesson - discarding.")
        return None

    # Simple overlap check: at least one heuristic substring matches
    set_a = {h.lower() for h in lesson_a.heuristics}
    set_b = {h.lower() for h in lesson_b.heuristics}
    overlap = any(
        any(word in b for word in a.split() if len(word) > 4)
        for a in set_a for b in set_b
    )

    if not overlap:
        print("[reflect] Cross-critique: lessons diverge - discarding both.")
        return None

    # Return the higher-confidence lesson
    return lesson_a if lesson_a.confidence >= lesson_b.confidence else lesson_b


def write_lesson_to_store(lesson: Lesson, store_path: str = "memory/lessons.jsonl") -> None:
    """
    Append an accepted lesson to the flat JSONL lesson store.
    In production, also embed and upsert to the vector store (memory/store.py).
    """
    os.makedirs(os.path.dirname(store_path), exist_ok=True)
    record = asdict(lesson)
    record["embedding"] = _embed(lesson.summary + " " + " ".join(lesson.heuristics))
    with open(store_path, "a") as f:
        f.write(json.dumps(record) + "\n")
    print(f"[reflect] Lesson written to {store_path}: {lesson.summary[:60]}...")


def reflect(
    trajectory: dict,
    outcome: str,
    trajectory_id: str,
    use_cross_critique: bool = True,
    confidence_threshold: float = 0.6,
    store_path: str = "memory/lessons.jsonl",
) -> Optional[Lesson]:
    """
    Top-level REFLECT entry point.
    Call with use_cross_critique=True for production; False for fast dev iteration.
    """
    if use_cross_critique:
        lesson = cross_critique(trajectory, outcome, trajectory_id, confidence_threshold)
    else:
        lesson = critique(trajectory, outcome, trajectory_id, confidence_threshold)

    if lesson is not None:
        write_lesson_to_store(lesson, store_path)

    return lesson
```

### Step 3 - Run the lab

```python
# Run from the repo root: python -c "from reflection.reflect import reflect; ..."
# or add this to a scratch script.

example_trajectory = {
    "task": "Write a Python function to parse ISO 8601 dates",
    "steps": [
        {"tool": "write_code", "input": "def parse_date(s): return datetime.fromisoformat(s)"},
        {"tool": "run_tests",  "output": "FAILED: timezone-aware strings not handled"},
        {"tool": "write_code", "input": "def parse_date(s): return datetime.fromisoformat(s.replace('Z', '+00:00'))"},
        {"tool": "run_tests",  "output": "PASSED"},
    ],
    "final_code": "def parse_date(s): return datetime.fromisoformat(s.replace('Z', '+00:00'))",
}

example_outcome = "PASS - all 8 test cases green after 2 attempts"

from reflection.reflect import reflect

lesson = reflect(
    trajectory=example_trajectory,
    outcome=example_outcome,
    trajectory_id="run-20260531-001",
    use_cross_critique=False,   # single pass for dev speed; set True for production
)

if lesson:
    print("Heuristics extracted:")
    for h in lesson.heuristics:
        print(f"  - {h}")
```

**Expected output** (model-dependent, illustrative):

```
[reflect] Lesson written to memory/lessons.jsonl: Python date parsing...
Heuristics extracted:
  - Always handle timezone suffix variants before calling fromisoformat
  - Write a test that includes a Z-suffix date as a fixture for any date parser
  - Prefer replace-then-parse over regex for simple timezone normalization
```

### Step 4 - Switch backends

```bash
# Run against VibeProxy (Claude subscription via local proxy)
# Note: ToS caveat - using a subscription via proxy may violate your provider's ToS.
AGENT_BACKEND=vibeproxy python -c "
from reflection.reflect import reflect
# ... same call as above
"

# Run against oMLX local model (no ToS concerns)
AGENT_BACKEND=omlx python -c "
from reflection.reflect import reflect
# ...
"
```

> [!note] Rate limits, not token costs
> On both backends you are rate-limited, not per-token-metered. Reflection loops that make many LLM calls (critique, cross-critique, re-rank) are effectively free in dollar terms. Design around throughput and local GPU/ANE capacity, not cost per call. This is a meaningful difference from the paid-API mental model where each reflective call has a direct dollar cost.

---

## 7. Extracting Reusable Heuristics and Failure Modes

The output of the critique step is only as useful as its downstream integration. Two categories of output have different memory destinations:

**Heuristics** - positive rules, stored as retrievable lessons in the vector store. Future runs with semantically similar tasks will retrieve these via embedding search (Module 04) and inject them into the system prompt.

**Failure modes** - negative rules, stored as anti-pattern entries. These are used in the VERIFY step (Module 07) to construct deterministic rejection rules: if the agent's proposed action matches a known failure mode, block it without an LLM call.

[ERL](https://arxiv.org/pdf/2603.24639) proposes keeping heuristics experience-linked - each lesson points back to the trajectory that generated it. This matters when a heuristic turns out to be wrong: you can retrace to the source trajectory, identify the bad outcome signal that caused the error, and prune the lesson rather than accumulating contradictory rules.

The [metacognitive position paper](https://openreview.net/forum?id=4KhDd0Ozqe) extends this argument: truly self-improving agents need meta-level awareness of which parts of their lesson store are reliable vs. tentative. A flat list of heuristics without provenance degrades over time.

---

## 8. Pitfalls

> [!danger] Recursive Drift
> As described in Section 3b: self-critique without external anchors produces confidently wrong lessons. **Every reflection run must have a ground-truth outcome signal** - test results, a benchmark score, a human annotation - before it writes to memory. Plausible-sounding LLM output is not ground truth. Forward reference: Module 07 and Module 10 provide the external anchoring mechanisms.

> [!warning] Lesson Accumulation Without Pruning
> A lesson store that only grows becomes a contradiction mine. Heuristics conflict. Retrieval returns stale advice. Build a TTL or confidence-decay mechanism from the start - easier than retrofitting it on 10,000 entries later.

> [!warning] In-Task Loops Without a Retry Budget
> Self-correction that retries without a max budget loops indefinitely on stuck states. Every retry path in `agent/loop.py` must have an explicit `max_retries` guard. When the budget runs out, fail fast and let the cross-task reflection path learn from the failure.

> [!tip] Cheap Calls Are Not Free Time
> Rate limits and local throughput are still finite. A critique call that takes 4 seconds on oMLX blocks the next run for 4 seconds. Design the REFLECT step to run asynchronously or in a post-run batch, not inline in the hot path.

> [!warning] Same-Model Bias in Self-Critique
> Asking the same model that acted to critique its own output produces systematically biased lessons - it cannot see its own blind spots. The cross-critique pattern in Section 5 mitigates this. For high-stakes lesson writes, use the VibeProxy (Claude) backend for critique even if oMLX handled the action step, or vice versa.

> [!example] ERL vs. In-Context Reflection
> A common mistake: adding "reflect on what went wrong" as a step inside the agent's system prompt and calling that ERL. It is not - that is in-context reflection, which is lost when the context window clears. ERL requires writing structured lessons to durable memory that outlives the context.

---

> [!question] Checkpoint
> Test your understanding before moving on.
>
> 1. A trajectory shows the agent correctly calling a tool but with the wrong argument format on the first attempt, then self-correcting on the second attempt and succeeding. The outcome is PASS. Should the cross-task REFLECT step produce a lesson? If yes, what kind?
>
> 2. You deploy the reflection system and notice that after 50 runs the agent has accumulated 47 heuristics, but its task success rate has dropped from 72% to 61%. What failure mode does this most likely indicate, and what is the correct remediation?
>
> 3. Why is the `confidence` field in the critique output insufficient as a sole quality gate? What does the multi-agent cross-critique add that single-pass self-scoring cannot provide?
>
> 4. Your oMLX model is running on a MacBook Air M2 with 16 GB RAM. Each critique call takes 6 seconds. You have a batch of 30 trajectories to reflect on. How should you structure the reflect pipeline to avoid blocking the next agent run?
>
> 5. A colleague proposes skipping the external outcome signal and using the agent's final self-assessment ("I believe this solution is correct") as the outcome for the REFLECT step. Name the failure mode this introduces and cite the two modules that provide the correct alternative.

---

## Navigation

← [[04 - Memory Systems]] · [[00 - Curriculum Map]] (home) · [[06 - Skill Acquisition and Curation]] →
