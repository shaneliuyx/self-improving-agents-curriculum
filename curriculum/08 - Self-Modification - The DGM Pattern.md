---
title: "Self-Modification - The DGM Pattern (Safely)"
tags: [self-improving-agents, curriculum, self-modification, dgm, evolution, evaluation]
module: 08
updated: 2026-06-08
---

# 08 · Self-Modification - The DGM Pattern (Safely)

**What you'll learn** - The [Darwin Godel Machine (DGM)](https://arxiv.org/abs/2505.22954) is a self-rewriting agent that treats its own code and prompt as evolvable artifacts: it samples a parent variant from an archive, mutates it (adding a tool, rewriting a system prompt, patching a helper function), evaluates the mutation on a fixed benchmark, and keeps the variant only if it outperforms its parent. This note covers that loop in full - the archive, the keep/discard gate, and how [SIA](https://arxiv.org/abs/2605.27276) extends it to weight updates. You will also learn why, for subscription/local builders, the safe version of DGM modifies the harness and prompt rather than model weights, how to use a large model for mutation proposals and a small local model for cheap eval runs, and where in the curriculum's ACT -> RECORD -> REFLECT -> LEARN -> VERIFY pipeline self-modification fits.

> [!info] Prerequisites
> - [[07 - Verification Gates and Layered Control]] - the eval gate that makes keep/discard safe
> - [[03 - The Minimal Agent Loop]] - the baseline loop being mutated
> - [[06 - Skill Acquisition and Curation]] - the skill archive pattern reused here

## Learning Objectives

- [ ] Explain the DGM archive loop: sample parent, mutate, evaluate, keep/discard, add to archive
- [ ] Contrast DGM (prompt/code mutation) with SIA (harness + weight updates) and identify which is safe for local/subscription builders
- [ ] Implement a minimal keep/discard self-modification loop over an agent's own system prompt
- [ ] Apply model routing: large model proposes mutations, small local model runs cheap evaluations
- [ ] Define the eval gate requirement: a mutation is kept only if it beats the parent on a fixed, sandboxed benchmark
- [ ] Explain why self-modification is restricted to narrow, benchmarkable, sandboxed sub-problems

---

## 1. The DGM Pattern - Core Idea

The [Darwin Godel Machine](https://arxiv.org/abs/2505.22954) moved SWE-bench pass rates from 20% to 50% by letting an agent iteratively rewrite its own coding tools and system prompt. The mechanism is deceptively simple:

1. **Archive** - a persistent store of (variant, score) pairs, seeded with the original agent
2. **Sample** - pick a parent from the archive (typically the highest-scoring variant, or with tournament selection)
3. **Mutate** - ask a large model to propose a change: "here is the current system prompt and tools; suggest one targeted improvement"
4. **Evaluate** - run the mutated agent on a fixed benchmark; compute its score
5. **Keep/Discard** - if the new score beats the parent's score, add the mutant to the archive; otherwise discard
6. **Repeat** - the archive grows with only improvements; the process is open-ended

This is "Darwin" (population-based selection) crossed with "Godel" (the agent can reason about and rewrite itself). The key safety property is that **mutations are never applied unconditionally** - the eval gate is the invariant.

### What Gets Mutated

In the original DGM paper, the agent rewrites Python tool code. For subscription/local builders, weight-level rewriting is not available - but that is fine, because the harness surface is large:

| Mutable surface | Examples |
|---|---|
| System prompt | Add a reasoning step, sharpen a constraint, add a few-shot example |
| Skill definitions | Rewrite a skill's docstring + implementation |
| Tool descriptions | Improve the description so the model calls it more reliably |
| Harness logic | Change how results are formatted, how context is truncated |
| Router rules | Adjust which tasks go to which model |

> [!note] SIA vs DGM
> [SIA (Self Improving AI)](https://arxiv.org/abs/2605.27276) from [hexo-ai](https://github.com/hexo-ai/sia) adds weight updates on top of the DGM loop - fine-tuning the model on trajectories that passed the eval gate. This is the "more aggressive" variant. For subscription/local builders: **skip weight updates, apply DGM at the harness/prompt layer only**. The [Continual Harness](https://arxiv.org/abs/2605.09998) paper formalizes this as "online adaptation" without retraining. A live proposal to wire SIA into a self-evolving agent as a harness-evolution skill is tracked in [hermes-agent-self-evolution #99](https://github.com/NousResearch/hermes-agent-self-evolution/issues/99).

> [!note] HyperAgents - the meta-agent rewrites its own harness
> [HyperAgents](https://arxiv.org/pdf/2603.19461) (Meta FAIR) pushes the DGM idea up one level: the meta-agent rewrites *its own code*, so the mechanism that **generates** improvements is itself subject to improvement - the paper calls this *metacognitive self-modification*. It also extends self-improvement past coding into non-coding tasks ([VentureBeat coverage](https://venturebeat.com/orchestration/meta-researchers-introduce-hyperagents-to-unlock-self-improving-ai-for-non-coding-tasks)). Same caution applies, only harder: a meta-agent that edits its own improvement loop needs an even stronger external VERIFY gate, because a single bad meta-mutation can corrupt every downstream mutation.

---

## 2. The Archive Loop - Diagram

```mermaid
%%{init: {"theme":"neutral","themeVariables":{"fontSize":"16px"},"flowchart":{"htmlLabels":true,"nodeSpacing":38,"rankSpacing":44,"padding":6,"useMaxWidth":true}}}%%
flowchart TD
    A[Archive<br/>seed: original agent v0] --> B[Sample parent<br/>highest score or tournament]
    B --> C[Propose mutation<br/>large model - claude-sonnet or qwen-72b]
    C --> D[Apply mutation<br/>write to temp variant dir]
    D --> E[Evaluate on benchmark<br/>small model for cheap runs]
    E --> F{score > parent score?}
    F -- yes --> G[Add variant to archive<br/>with new score]
    F -- no --> H[Discard variant<br/>no archive change]
    G --> B
    H --> B
```

*The DGM archive loop: only improvements enter the archive, so the population monotonically improves on the benchmark. Model routing splits the expensive mutation step from the cheap evaluation step.*

---

## 3. Variant Lifecycle - Diagram

```mermaid
%%{init: {"theme":"neutral","themeVariables":{"fontSize":"16px"}}}%%
stateDiagram-v2
    [*] --> Proposed : mutate from parent
    Proposed --> Evaluating : eval gate triggered
    Evaluating --> Accepted : score > parent score
    Evaluating --> Rejected : score <= parent score
    Accepted --> Archived : stored with score
    Rejected --> [*] : discarded
    Archived --> Proposed : sampled as next parent
```

*A variant's lifecycle: it is proposed from a parent, evaluated on the fixed benchmark, then either archived (and eligible to become a parent) or discarded. Rejected variants leave no trace in the archive.*

---

## 4. Model Routing in the DGM Loop

The [community consensus](https://www.reddit.com/r/AI_Agents/comments/1taei9m/stop_building_ai_agents/) on model routing applies directly here: don't use the large model for every call. DGM has a natural split:

- **Mutation proposal** - requires creativity, understanding of the agent's purpose, and knowledge of what changes might help. Use the large model (`claude-sonnet-4-5-20250929` via VibeProxy, or `Qwen2.5-Coder-14B-Instruct-4bit` via oMLX).
- **Evaluation runs** - requires only task execution, not reasoning about the agent itself. Use the small local model (`qwen2.5-coder-7b` via oMLX). These can be batched and run fast.

This matches the [Autodidact](https://github.com/BuffaloTechRider/Autodidact) local-first pattern: keep the slow, expensive model out of the inner eval loop.

> [!warning] Rate Limits vs Token Cost
> Both oMLX and VibeProxy are rate-limited, not per-token-metered. Many eval runs are cheap in dollar terms but can saturate local throughput. Design the eval loop to run evaluations sequentially or in small batches. The mutation-proposal step (one large-model call per iteration) is the bottleneck to manage against VibeProxy rate limits.

---

## 5. Why Narrow and Benchmarkable

Self-modification without a reliable eval gate is recursive drift - the agent "improves" on a proxy metric while degrading on real tasks. The DGM paper's result (20% -> 50% on SWE-bench) holds because SWE-bench is a fixed, external benchmark that cannot be gamed by prompt changes.

> [!warning] The compounding ceiling - self-improvement often stalls at iteration one
> A 2026 study of [1,000+ harness experiments](https://aiweekly.co/alerts/ai-agents-hit-self-improvement-wall-after-one-pass) found agents reliably propose **one** structural harness improvement but then fail to **compound** it across later iterations. The plateau is attributed not to model size but to a missing **self-model** - the agent has no internal account of *why* the first change worked, so it cannot build on it. This puts a concrete ceiling on the "self-improvement compounds with capability" assumption, at iteration one. Practical takeaway for this module: do not assume your keep/discard loop will keep climbing on its own. Expect a fast first gain, then diminishing returns - and treat each accepted mutation as a deliberate, separately-verified step, not a self-sustaining ratchet.

For your own agent, the rule is: **only attempt DGM-style self-modification on sub-problems where you can write a real eval set in under an hour**. Good candidates:

- "Does the agent correctly parse the output format?" (5-10 test cases)
- "Does the agent call the right tool for these 8 query types?"
- "Does the reflection step produce a non-empty lesson on failure trajectories?"

Bad candidates: "Is the agent more helpful?" (unmeasurable), "Does the agent write better code?" (expensive to evaluate).

The [[10 - Evaluation Harness]] module covers building eval sets. The [[09 - Sandboxing and Safe Execution]] module covers running mutated code without damaging your system - always required before self-modification loops.

> [!danger] Never Self-Modify Without a Sandbox
> Mutated tool code runs on your machine. Before starting any self-modification loop, ensure the eval environment is sandboxed. See [[09 - Sandboxing and Safe Execution]]. The [Airlock](https://github.com/airlockrun/airlock/) project (self-upgrading compiled agents) and [Containarium](https://github.com/footprintai/Containarium) (MCP-native sandbox) are purpose-built for this. Skipping sandboxing means a bad mutation can delete files, corrupt state, or exfiltrate data.

---

## 6. The Scaffold Layout

The runnable lab uses two scaffold paths:

```
evolve/loop.py       # the keep/discard loop
evolve/archive/      # persisted variants as JSON files
evals/tasks.py       # the fixed eval set
evals/run.py         # runner that scores a variant
```

The `evolve/archive/` directory stores variant files named `v{n}.json` with fields: `system_prompt`, `score`, `parent_id`, `iteration`.

---

## 7. Hands-On Lab - Minimal Keep/Discard Self-Modification Loop

This lab implements a keep/discard loop that mutates the agent's own system prompt and scores each variant on a tiny eval set. It maps directly to `evolve/loop.py` in the scaffold.

### Step 1 - Define a Tiny Eval Set

Create `evals/tasks.py` with five deterministic test cases:

```python
# evals/tasks.py
# Each task: input text -> expected keyword in the agent's response.
# Simple enough to run fast; real enough to catch regressions.

TASKS = [
    {
        "id": "t1",
        "user": "List three benefits of immutable data structures.",
        "must_contain": ["immutable", "side effect"],
    },
    {
        "id": "t2",
        "user": "What is the difference between a list and a tuple in Python?",
        "must_contain": ["mutable", "tuple"],
    },
    {
        "id": "t3",
        "user": "Explain what a context manager does in one sentence.",
        "must_contain": ["with", "__exit__"],
    },
    {
        "id": "t4",
        "user": "What does the walrus operator do?",
        "must_contain": [":=", "assign"],
    },
    {
        "id": "t5",
        "user": "Name two Python built-ins for functional programming.",
        "must_contain": ["map", "filter"],
    },
]
```

### Step 2 - Eval Runner

```python
# evals/run.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backends.adapter import make_client
from evals.tasks import TASKS


def score_variant(system_prompt: str, backend: str = None) -> float:
    """
    Score a system prompt variant against the fixed eval set.
    Returns fraction of tasks passed (0.0 - 1.0).
    Uses the SMALL local model for cheap, fast evaluation.
    """
    # Always use oMLX for eval runs - cheap, local, no rate-limit pressure on VibeProxy
    client, model = make_client("omlx")
    passed = 0
    for task in TASKS:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task["user"]},
            ],
            max_tokens=256,
            temperature=0.0,
        )
        text = resp.choices[0].message.content.lower()
        if all(kw.lower() in text for kw in task["must_contain"]):
            passed += 1
    return passed / len(TASKS)
```

### Step 3 - Archive Helpers

```python
# evolve/archive/__init__.py
import json
import os
from pathlib import Path

ARCHIVE_DIR = Path(__file__).parent


def load_archive() -> list[dict]:
    variants = []
    for f in sorted(ARCHIVE_DIR.glob("v*.json")):
        variants.append(json.loads(f.read_text()))
    return variants


def save_variant(variant: dict) -> None:
    n = len(list(ARCHIVE_DIR.glob("v*.json")))
    path = ARCHIVE_DIR / f"v{n:04d}.json"
    path.write_text(json.dumps(variant, indent=2))


def best_variant(archive: list[dict]) -> dict:
    return max(archive, key=lambda v: v["score"])
```

### Step 4 - The Keep/Discard Loop

```python
# evolve/loop.py
"""
Minimal DGM-style keep/discard self-modification loop.
- Uses the LARGE model to propose mutations (VibeProxy=claude-sonnet, oMLX=qwen-72b)
- Uses the SMALL local model for eval runs (always oMLX qwen2.5-coder-7b)

Run:
    AGENT_BACKEND=vibeproxy python evolve/loop.py --iterations 5
    AGENT_BACKEND=omlx      python evolve/loop.py --iterations 5
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backends.adapter import make_client
from evolve.archive import load_archive, save_variant, best_variant
from evals.run import score_variant

SEED_PROMPT = """You are a helpful Python tutor. Answer questions about Python
concisely and accurately. Include code examples when they clarify your answer."""

MUTATION_META_PROMPT = """\
You are a prompt engineer. Below is a system prompt used by a Python tutor agent
and its current benchmark score (fraction of 5 test cases passed).

Current system prompt:
---
{current_prompt}
---
Current score: {score:.2f}

Propose ONE targeted improvement to the system prompt that might increase the score.
Respond with ONLY the new system prompt - no explanation, no preamble, no markdown fences.
The new prompt must be a complete replacement, not a diff."""


def propose_mutation(current_prompt: str, score: float, backend: str) -> str:
    """Use the large model to propose a mutated system prompt."""
    client, model = make_client(backend)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": MUTATION_META_PROMPT.format(
                    current_prompt=current_prompt, score=score
                ),
            }
        ],
        max_tokens=512,
        temperature=0.8,  # some creativity for mutations
    )
    return resp.choices[0].message.content.strip()


def run_loop(iterations: int, backend: str) -> None:
    archive = load_archive()

    # Seed the archive if empty
    if not archive:
        print("Seeding archive with v0000...")
        seed_score = score_variant(SEED_PROMPT)
        seed = {
            "id": "v0000",
            "system_prompt": SEED_PROMPT,
            "score": seed_score,
            "parent_id": None,
            "iteration": 0,
        }
        save_variant(seed)
        archive = [seed]
        print(f"Seed score: {seed_score:.2f}")

    for i in range(1, iterations + 1):
        parent = best_variant(archive)
        print(f"\n--- Iteration {i} | parent={parent['id']} score={parent['score']:.2f} ---")

        # Propose mutation using the large model
        print(f"Proposing mutation via {backend}...")
        mutated_prompt = propose_mutation(parent["system_prompt"], parent["score"], backend)

        # Evaluate mutation using the small local model
        print("Evaluating mutation via oMLX (small model)...")
        new_score = score_variant(mutated_prompt, backend="omlx")
        print(f"Mutation score: {new_score:.2f}")

        if new_score > parent["score"]:
            n = len(archive)
            variant_id = f"v{n:04d}"
            variant = {
                "id": variant_id,
                "system_prompt": mutated_prompt,
                "score": new_score,
                "parent_id": parent["id"],
                "iteration": i,
            }
            save_variant(variant)
            archive.append(variant)
            print(f"KEPT as {variant_id} (improvement: +{new_score - parent['score']:.2f})")
        else:
            print(f"DISCARDED (no improvement over {parent['score']:.2f})")

    final = best_variant(archive)
    print(f"\nFinal best: {final['id']} score={final['score']:.2f}")
    print("System prompt:")
    print(final["system_prompt"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=5)
    args = parser.parse_args()
    backend = os.getenv("AGENT_BACKEND", "omlx")
    run_loop(args.iterations, backend)
```

### Running the Lab

```bash
# Using oMLX for both mutation proposals and eval (all local)
AGENT_BACKEND=omlx python evolve/loop.py --iterations 5

# Using VibeProxy for mutation proposals, oMLX for eval (hybrid)
# Note: VibeProxy routes your Claude MAX subscription via local proxy.
# Using a subscription via proxy may violate provider ToS - check before use.
AGENT_BACKEND=vibeproxy python evolve/loop.py --iterations 5

# Inspect the archive after the run
ls evolve/archive/
cat evolve/archive/v0002.json
```

Expected output pattern:

```
Seeding archive with v0000...
Seed score: 0.40

--- Iteration 1 | parent=v0000 score=0.40 ---
Proposing mutation via omlx...
Evaluating mutation via oMLX (small model)...
Mutation score: 0.60
KEPT as v0001 (improvement: +0.20)

--- Iteration 2 | parent=v0001 score=0.60 ---
...
DISCARDED (no improvement over 0.60)
```

> [!example] What Good Mutations Look Like
> After a successful run, open `evolve/archive/v0002.json` and compare the system prompt to the seed. A typical improvement: the mutated prompt explicitly instructs the model to include `__exit__` in context manager explanations, or to always mention `:=` by name for walrus operator questions. These are targeted, verifiable changes - exactly the DGM pattern.

---

## 8. Pitfalls

> [!warning] Pitfall 1 - The Eval Set Leaks Into the Mutation
> If the large model can see the eval task text when proposing mutations, it will overfit the system prompt to the test cases. Keep `evals/tasks.py` out of the mutation meta-prompt. The `MUTATION_META_PROMPT` in the lab above shows only the current score, not the tasks. The [DGM paper](https://arxiv.org/abs/2505.22954) addresses this as "evaluation leakage" - use a held-out test set separate from the optimization target.

> [!warning] Pitfall 2 - Score Plateaus and Noise
> With only 5 eval tasks, a single lucky run can score 1.0 trivially. Use at least 20-50 tasks for a meaningful signal. Also, LLM outputs are stochastic - run each variant 3 times and average the scores before making a keep/discard decision. See [[10 - Evaluation Harness]] for proper eval design.

> [!danger] Pitfall 3 - Unsandboxed Mutation of Tool Code
> The lab above mutates only the system prompt (a string), which is safe. If you extend this to mutate actual Python tool code, every mutation runs as executable code on your machine. Always sandbox first - see [[09 - Sandboxing and Safe Execution]]. The [Airlock](https://github.com/airlockrun/airlock/) pattern (compile + isolate) and [Containarium](https://github.com/footprintai/Containarium) (MCP-native sandbox) are the right infrastructure.

> [!warning] Pitfall 4 - Open-Ended Mutation Without a Stop Condition
> The DGM loop can run indefinitely. Always set an iteration budget and a "score ceiling" (e.g., stop at 0.90 or after 20 iterations without improvement). Without a stop condition, you accumulate archive bloat and burn through VibeProxy rate limits.

> [!note] Pitfall 5 - Layer 0 Violations
> The [NousResearch hermes-agent finding](https://github.com/NousResearch/hermes-agent/issues/29652) established the rule priority hierarchy: L0 (core identity) > L1 (prompt) > L2 (deterministic scripts) > L3 (global safety). DGM operates at L1 (prompt mutation). Never allow mutations to propose changes that override L0 or L3 constraints. The mutation meta-prompt should explicitly instruct the proposer: "do not change safety constraints or identity statements."

---

## 9. Connecting to the Canonical Loop

Self-modification is the LEARN step in the ACT -> RECORD -> REFLECT -> LEARN -> VERIFY pipeline, but with the highest stakes:

| Step | Module | DGM role |
|---|---|---|
| ACT | 03 | The baseline agent being evolved |
| RECORD | 04 | Archive stores variants + scores |
| REFLECT | 05 | Mutation proposal: "what change might help?" |
| LEARN | 08 (this note) | Apply mutation, update archive |
| VERIFY | 07, 10 | Eval gate: keep only if score improves |

The curriculum's thesis is that camps (1) and (2) differ in risk: DGM/SIA (camp 1, code/weight mutation) requires a strong VERIFY gate to be safe; skill accumulation (camp 2, Module 06) is safer because skills are additive, not mutating existing behavior. For subscription/local builders, camp 1 is reserved for narrow, benchmarkable sub-problems where the eval gate is reliable.

The [Autodidact](https://github.com/BuffaloTechRider/Autodidact) and [Komi-learn](https://github.com/kurikomi-labs/komi-learn) projects both implement the camp 2 path (memory + skill accumulation) without self-modification, which is the pragmatic default. Use DGM only when you have a specific, measurable sub-problem and the eval set to gate it.

---

> [!question] Checkpoint
> 1. What is the role of the archive in the DGM loop, and why does it guarantee monotonic improvement on the benchmark?
> 2. In the lab, the mutation proposal uses the large model but evaluation uses the small local model. What is the rationale, and how does this interact with VibeProxy rate limits?
> 3. Why is prompt mutation (as in the lab) safer than tool-code mutation, and what additional infrastructure is required before extending the loop to mutate executable code?
> 4. The eval set in the lab has only 5 tasks. What two problems does this cause, and how would you fix them before using the loop in production?
> 5. SIA adds weight updates on top of the DGM loop. Why is this unavailable to subscription/local builders, and what do they use instead?

---

## Navigation

← [[07 - Verification Gates and Layered Control]] · [[00 - Curriculum Map]] (home) · [[09 - Sandboxing and Safe Execution]] →
