# agent/classify_project.py
# Usage:
#   AGENT_BACKEND=omlx python agent/classify_project.py
#   AGENT_BACKEND=vibeproxy python agent/classify_project.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backends.adapter import make_client

DECISION_PROMPT = """You are a system architect applying the four-question decision framework.

Given a project description, answer these questions in order:
1. Can you draw it as clear sequential steps? (yes -> Automation)
2. Does it have more than 5 branches with unpredictable inputs? (no -> Automation)
3. Is the cost of the worst-case wrong answer high? (yes -> Automation)
4. Will compliance or legal review it? (yes -> Automation)
5. Does it need to improve across runs? (no -> Agent)
6. Can improvement be bounded and verified? (no -> Agent; yes -> Self-Improving Agent)

Respond with:
- Classification: [Automation | Agent | Self-Improving Agent]
- Recommended improvement axis: [None | Memory | Skills | Prompt | Code | Weights]
- One-sentence rationale.
- Top risk if you build the more complex option anyway.

Project description: {description}"""

def classify(description: str) -> str:
    client, model = make_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": DECISION_PROMPT.format(description=description)}
        ],
        temperature=0.2,
        max_tokens=300,
    )
    return response.choices[0].message.content

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
