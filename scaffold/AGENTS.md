# Agent Operating Contract

Read this at the start of every session. This is your L1 (Prompt-layer)
operating contract. L2 deterministic scripts (scripts/go, scripts/commit)
take precedence over this text when they conflict.

---

## Session Protocol

Every iteration follows this loop:

```
ACT -> RECORD -> REFLECT -> LEARN
         (gated by VERIFY at every LEARN step)
```

### ACT
- Read GOAL.md. That one sentence is your north star.
- Attempt the assigned task using available tools.
- Be concise. Prefer tool calls over speculation.
- Stop after a maximum of 10 tool-call rounds per task.

### RECORD
- After each task, save the full trajectory to memory/store.py.
- Include: task input, every tool call + result, final answer, success flag.
- Do not summarise away failures - raw failure data is the most valuable
  learning signal.

### REFLECT
- Call reflection/reflect.py with the trajectory and outcome.
- Produce structured lessons: what worked, what failed, root cause,
  corrective heuristic.
- Anchor every lesson to an observed outcome, not a guess.

### LEARN
- Proposed changes fall into two categories:
  (a) New skill: save to skills/SKILLS/ via skills/library.py
  (b) System-prompt variant: run evolve/loop.py to evaluate the mutation
- NEVER apply a change without a passing verification gate.
- Run verification/gates.py before any LEARN step is accepted.
- If the gate returns REJECT or ESCALATE, discard the proposal.

### VERIFY (the gate that prevents recursive drift)
- Every proposed improvement must pass evals/run.py before being kept.
- A candidate is accepted only if it scores strictly better than the
  current baseline on the eval set. Ties are discarded.
- Regression = automatic discard. No exceptions.

---

## What you MUST NOT do

- Do not modify any file outside the project directory.
- Do not delete or overwrite AGENTS.md, GOAL.md, or verification/gates.py
  without a passing eval gate.
- Do not run scripts with --force or override git hooks.
- Do not call external APIs or the internet (embeddings go to localhost:8000,
  generation goes to localhost:8000 or localhost:8317).
- Do not silently swallow errors. Surface them in the trajectory record.

---

## Checkpoint protocol

After every accepted LEARN step:
1. Run `scripts/commit "reason for change"`.
2. Every commit is a safe restore point.
3. If the next eval run regresses, `git revert HEAD` and restart.

---

## Layer priority reminder

L0 Core identity (non-overridable)
L1 This file (AGENTS.md) - you are reading it
L2 Deterministic scripts (scripts/go, scripts/commit) - override L1 on conflicts
L3 Global safety rules

Production experience (NousResearch hermes-agent #29652) shows that L1 prompt
instructions alone are unreliable - agents skip them under pressure. Critical
invariants are encoded in L2 scripts, not prose.
