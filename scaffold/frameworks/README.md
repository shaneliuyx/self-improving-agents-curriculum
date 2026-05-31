# frameworks/ — the optional "graduation" track

The core lab is built on the **raw OpenAI SDK** on purpose: self-improving agents
rewrite their own loop, memory, and skills, so you need a loop you fully control
and can *see*. Our investigation of the 2026 self-improving-agent projects backs
this up — SIA, Nerve, komi-learn, Autodidact, agent-seed and friends all run on
raw SDKs, the Claude Agent SDK, or custom harnesses. **None** use LangChain /
CrewAI / AutoGen.

Once you understand the mechanics, a framework buys you maintained plumbing. The
adapters here show how to swap a hand-built piece for a popular framework
**without changing your backends** — every one targets oMLX (`:8000`) or
VibeProxy (`:8317`) through a custom OpenAI-compatible `base_url`.

| Adapter | Replaces | Framework | Why |
|---|---|---|---|
| `mem0_memory.py` | `memory/store.py` (Module 04/06) | [mem0](https://github.com/mem0ai/mem0) (57k★) | Most popular memory layer; free dedup + scoping + extraction |
| `pydantic_ai_loop.py` | `agent/loop.py` (Module 03) | [Pydantic AI](https://github.com/pydantic/pydantic-ai) (17k★) | Cleanest, least-opaque ReAct loop; one-line `base_url` |
| `claude_agent_sdk_loop.py` | `agent/loop.py` (Module 03) | [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python) | What SIA + Nerve use; Claude **subscription** track (no API key, no VibeProxy) |

## Install + run

```bash
pip install -e ".[frameworks]"        # adds mem0ai + pydantic-ai
# with a backend running (oMLX :8000 or VibeProxy :8317):
python -m frameworks.pydantic_ai_loop
python -m frameworks.mem0_memory      # needs oMLX :8000 for local embeddings
```

## The one rule that still holds

Generation backend is swappable; **embeddings are always local** (oMLX). mem0's
embedder is pinned to `EMBED_BASE_URL` for exactly this reason — VibeProxy has no
embeddings endpoint.

## Not covered here (by design)

- **LangGraph / CrewAI / OpenAI Agents SDK / Strands** — all accept a custom
  `base_url` too, but add more abstraction than the lab needs. See note
  `13 - Graduating to a Framework` for the full comparison.
