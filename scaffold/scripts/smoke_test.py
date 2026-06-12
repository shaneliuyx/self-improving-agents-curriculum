# scripts/smoke_test.py
# Smoke test: verify both backends respond and embeddings work locally.
# Reconciled from:
#   - note 00 (scripts/smoke_test.py): ping(backend) / ping_embeddings() style
#   - note 02 (labs/02_smoke_test.py): richer test_chat / test_embeddings / test_model_routing style
#
# Run with:
#   AGENT_BACKEND=omlx      python scripts/smoke_test.py
#   AGENT_BACKEND=vibeproxy python scripts/smoke_test.py

import os
import sys
from openai import OpenAI
from backends.adapter import make_client

PROMPT = "Reply with exactly one sentence: what is 2 + 2 and why?"


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
    for test_fn in (test_chat, test_embeddings, test_model_routing):
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
