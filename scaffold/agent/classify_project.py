# agent/classify_project.py
# Usage:
#   AGENT_BACKEND=omlx python agent/classify_project.py
#   AGENT_BACKEND=vibeproxy python agent/classify_project.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backends.adapter import make_client

DECISION_PROMPT = """You are a system architect. Classify a project into EXACTLY ONE of three build
types using the framework below, then pick ONE improvement axis. Follow the definitions and the
decision procedure LITERALLY — do not invent your own criteria, and do not let the word "learns" or
"adapt" in the project description override the rules (many projects say "learn" but are still Agents).

ASSUME the project will be built as an LLM-based system — the question is which of the three
LLM-system SHAPES fits, NOT "LLM vs classic ML / vs a trained classifier." So an LLM reasoning over
open-ended, unstructured input (any free-form natural language, document, or request) is AT LEAST an
Agent — never Automation — even if the output is a small fixed set of categories. "Automation" here
means a deterministic pipeline whose *inputs* are structured/predictable, not "a model does the work."

## The three build types

- **Automation** — a fixed, mostly-deterministic pipeline (few branches, an LLM is optional). Pick it
  when EITHER the task is predictable sequential steps, OR a wrong answer is high-stakes /
  compliance-gated (you want a deterministic, auditable path). NOTE: free-text / open-ended input
  is NOT predictable — classifying arbitrary natural-language input is NOT Automation just because the
  output set is small.
- **Agent** — an LLM-driven loop that reasons over UNPREDICTABLE, open-ended input and chooses among
  many branches at runtime, using a FIXED model + prompt that does NOT change across runs. Pick it when
  the input is open-ended and the cost of a wrong answer is low, AND either it does not need to get
  better run-over-run, OR it does but that improvement cannot be objectively bounded/verified.
- **Self-Improving Agent** — an Agent that MEASURABLY improves across runs from its own experience,
  where that improvement is BOUNDED and VERIFIABLE: you can name a metric that should go up and a
  rollback when it goes down. Pick it ONLY when BOTH hold: (a) it must improve across runs, AND (b) the
  improvement signal is bounded + verifiable. If improvement is desired but NOT verifiable, it is an
  Agent (self-improvement would silently drift).

## Decision procedure (apply IN ORDER; the FIRST rule that fires wins)

1. Predictable, sequential steps with few branches AND structured/predictable input
   (NOT free-form natural-language text)? -> **Automation**
   (Classifying, tagging, or triaging arbitrary free-text input FAILS this rule — the input is
    open-ended — so it is NOT Automation; continue to the rules below.)
2. Worst-case wrong answer high-stakes, OR compliance/legal must sign off? -> **Automation**
3. Input is open-ended but the system does NOT need to improve across runs? -> **Agent**
4. It should improve across runs, but the improvement CANNOT be bounded + verified
   (no objective metric, no rollback)? -> **Agent**
5. Otherwise — improves across runs AND the signal is bounded + verifiable -> **Self-Improving Agent**

## Improvement axis (pick the LIGHTEST one that delivers the needed improvement)

- **None** — Automation, OR any Agent that does not change its behavior across runs. An Agent that
  merely READS a fixed dataset for context, or uses feedback only within a single session, is NOT
  learning -> None. The Memory/Skills/Prompt/Code/Weights axes below describe HOW a *Self-Improving
  Agent* improves — so if Classification is Agent (not Self-Improving), the axis is almost always
  None; if Automation, ALWAYS None.
- **Memory** — improves by accumulating + retrieving past cases/feedback across runs (learns from its
  own history). Default axis for a Self-Improving Agent that learns from its own runs.
- **Skills** — improves by adding/refining reusable tools or procedures it can call.
- **Prompt** — improves by editing its own instructions/templates.
- **Code** — improves by writing/modifying its own code paths.
- **Weights** — improves by fine-tuning model weights (heaviest; rarely justified).

## Output format — emit ONLY these four lines, with these EXACT labels, in this order, no preamble:

- **Classification:** <Automation | Agent | Self-Improving Agent>
- **Recommended improvement axis:** <None | Memory | Skills | Prompt | Code | Weights>
- **Rationale:** <one sentence naming WHICH decision rule (1-5) fired and why>
- **Top risk if you build the more complex option anyway:** <one sentence>

## Worked examples (different domains — use them only to learn the FORMAT and the rule mapping)

Project: "Generate a weekly sales summary email from a fixed SQL query."
- **Classification:** Automation
- **Recommended improvement axis:** None
- **Rationale:** Rule 1 — predictable sequential steps (query -> format -> send), few branches, no learning needed.
- **Top risk if you build the more complex option anyway:** An agent adds nondeterminism + cost to a task a cron job does reliably.

Project: "Triage open-ended customer emails and draft replies; the model does not learn across emails."
- **Classification:** Agent
- **Recommended improvement axis:** None
- **Rationale:** Rule 3 — open-ended input needs flexible reasoning, low stakes, but it does not improve across runs.
- **Top risk if you build the more complex option anyway:** A self-improving loop optimizes a proxy (e.g. reply speed) and drifts from answer quality with no rollback.

Project: "Support bot that uses thumbs-up/down on its past answers to raise its resolution rate over time."
- **Classification:** Self-Improving Agent
- **Recommended improvement axis:** Memory
- **Rationale:** Rule 5 — must improve across runs AND the signal (resolution rate) is bounded + verifiable.
- **Top risk if you build the more complex option anyway:** Training-signal corruption — biased/adversarial feedback silently degrades answers before it is detected.

Now classify the project below. Output ONLY the four labeled lines.

Project: {description}"""

def classify(description: str) -> str:
    client, model = make_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": DECISION_PROMPT.format(description=description)}
        ],
        temperature=0.0,   # deterministic — this is a classification, not generation
        max_tokens=320,
    )
    return response.choices[0].message.content or ""

if __name__ == "__main__":
    scenarios = [
        "Auto-tag incoming support tickets by category using past ticket data.",
        "Help draft and iterate technical blog posts with style feedback.",
        "Coding assistant that learns from past PR review comments across projects.",
    ]
    backend = os.getenv("AGENT_BACKEND", "omlx")
    print(f"Backend: {backend}\n{'='*60}")
    for i, scenario in enumerate(scenarios, 1):
        print(f"\nScenario {i}: {scenario}")
        print("-" * 40)
        result = classify(scenario)
        print(result)
