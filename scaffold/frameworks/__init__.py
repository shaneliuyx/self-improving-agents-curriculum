"""
frameworks/ - OPTIONAL "graduation" adapters.

The core lab (agent/, memory/, reflection/, skills/, verification/, evolve/) is
deliberately built on the raw OpenAI SDK so every step of the loop is visible.
This package shows how to swap a hand-built piece for a popular framework once
you understand what it does - WITHOUT changing your backends. Every adapter here
targets the same oMLX (:8000) / VibeProxy (:8317) endpoints via a custom base_url.

Install the optional deps first:
    pip install -e ".[frameworks]"

Modules:
    mem0_memory     - mem0 as a drop-in for memory/store.py (Module 04/06)
    pydantic_ai_loop - Pydantic AI as a drop-in for agent/loop.py (Module 03)

These imports are guarded: importing this package never fails even if the
optional framework deps are not installed.
"""
