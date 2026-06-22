# scripts/smoke_test.py
# Smoke test for the lab agent built on agentkit.
#
#   test_lab_agent_offline  ALWAYS runs (no network): composes the agentkit-based
#                           SelfImprovingAgent with a FAKE LLMClient and proves
#                           the wiring runs end-to-end.
#   test_chat / test_embeddings / test_model_routing  need a REAL backend up.
#
# Run with:
#   python scripts/smoke_test.py                      # offline check always runs
#   AGENT_BACKEND=omlx      python scripts/smoke_test.py
#   AGENT_BACKEND=vibeproxy python scripts/smoke_test.py

import os
import sys
from pathlib import Path

# Allow `python scripts/smoke_test.py` from the repo root (project root on path).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI
from backends.adapter import make_client

PROMPT = "Reply with exactly one sentence: what is 2 + 2 and why?"


class _FakeClient:
    """A no-network agentkit ``LLMClient`` for the offline composition check."""

    def chat(self, messages, tools=None):
        from agentkit.types import ChatResult
        return ChatResult(text="The answer is 391.", total_tokens=0)


def test_lab_agent_offline():
    """Compose the agentkit-based lab agent with a fake client - NO network.

    Proves the refactor's central claim: the lab agent IS agentkit's
    SelfImprovingAgent, wired by lab_agent.build_lab_agent, and it runs.
    """
    import tempfile
    from lab_agent import build_lab_agent, lab_eval_set

    print("\n[Lab agent on agentkit] offline composition (fake client)")
    cfg = tempfile.mkdtemp()
    agent = build_lab_agent(backend=_FakeClient(), with_memory=False, config_dir=cfg)
    print(f"  roles loaded: {sorted(agent.roles)}")
    result = agent.run("What is 17 * 23? Use the calculator tool.")
    print(f"  run answer: {result.answer!r}")
    assert result.answer, "agent.run returned an empty answer"
    pairs = lab_eval_set()
    assert pairs and all(len(p) == 2 for p in pairs), "eval set malformed"
    print(f"  eval set: {len(pairs)} (task, expected) pairs")
    print("  PASS")


def test_chat():
    backend = os.getenv("AGENT_BACKEND", "omlx")
    client, model = make_client()
    print(f"\n[Chat] backend={backend}  model={model}")
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": PROMPT}],
        max_tokens=80,
        temperature=0.0,
    )
    text = resp.choices[0].message.content.strip()
    print(f"  Response: {text}")
    assert len(text) > 5, "Response too short - backend may not be running"
    print("  PASS")


def test_embeddings():
    # Always oMLX regardless of AGENT_BACKEND
    embed_model = os.getenv("EMBED_MODEL", "nomic-embed-text")
    client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")
    print(f"\n[Embeddings] model={embed_model}  (always oMLX :8000)")
    result = client.embeddings.create(model=embed_model, input="hello world")
    vec = result.data[0].embedding
    assert len(vec) > 10, "Embedding vector is too short"
    print(f"  Vector dims: {len(vec)}")
    print("  PASS")


def test_model_routing():
    from backends.router import route
    from backends.adapter import chat
    print(f"\n[Routing] backend={os.getenv('AGENT_BACKEND', 'omlx')}")
    for difficulty in ("easy", "hard"):
        d = route(difficulty)
        reply = chat([{"role": "user", "content": f"difficulty={difficulty}: say OK"}],
                     backend=d.backend, model=d.model, max_tokens=10)
        print(f"  {difficulty:5s} -> backend={d.backend} model={d.model}  reply={reply.strip()!r}")
    print("  PASS")


if __name__ == "__main__":
    errors = []
    # Offline composition check first (always runs), then the real-backend tests.
    for test_fn in (test_lab_agent_offline, test_chat, test_embeddings, test_model_routing):
        try:
            test_fn()
        except Exception as e:
            errors.append(f"{test_fn.__name__}: {e}")
            print(f"  FAIL: {e}")

    print("\n--- Summary ---")
    if errors:
        print(f"FAILED ({len(errors)} errors):")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("All checks passed.")
