---
description: Refresh the "Building Self-Improving Agents" curriculum from the last 30 days of sources, update notes + scaffold, audit consistency, and push to GitHub.
argument-hint: "[optional extra focus, e.g. 'memory systems' or a new subtopic]"
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, Skill, Workflow, WebSearch, AskUserQuestion
---

# /improve-curriculum - self-improving the curriculum

You are running the maintenance loop for the **Building Self-Improving Agents** curriculum.
This applies the curriculum's own ACT -> RECORD -> REFLECT -> LEARN -> VERIFY thesis to itself:
gather fresh evidence, learn what changed, update the material, VERIFY consistency, then ship.

## Fixed paths (this machine)
- CURRICULUM (Obsidian notes): `/Users/yuxinliu/第二大脑/Self-Improving Agents`
- SCAFFOLD (runnable lab):     `/Users/yuxinliu/self-improving-agent-lab`
- REPO (git, pushes to GH):    `/Users/yuxinliu/self-improving-agents-curriculum`
- SPEC (authoring contract):   `<REPO>/tools/curriculum-spec.md`  - READ THIS FIRST (house style, citations, conventions, the full note list, backend facts)
- Refresh script:              `<REPO>/tools/refresh-research.sh`  (reproducible last30days engine call)
- Improvement workflow:        `<REPO>/tools/improve-workflow.js`  (parallel note updates + audit)
- Research output dir:         `~/.claude/plugins/data/last30days-last30days-skill/research`
- Optional focus argument:     $ARGUMENTS

## Protocol (do EVERY step; keep a human in the loop on the final push)

### 1. GATHER (fresh evidence)
- Invoke the `/last30days` skill for `building self-improving agents` (weave in `$ARGUMENTS` if given).
  If the skill is unavailable in this context, run `bash <REPO>/tools/refresh-research.sh "$ARGUMENTS"`
  which writes a raw `*-raw-refresh.md` to the research dir. Read that raw file in full.
- Run 2-3 `WebSearch` supplements for anything new since the last run (papers, Show HN, releases, tools).
- RECORD: copy/save the new findings into `<REPO>/research/` with a dated filename.

### 2. REFLECT (gap analysis)
- Read the SPEC and the current 13 notes (`00 - ...` .. `12 - ...`). Read the new research.
- Produce a concrete CHANGE LIST: per note, what new citation / section / diagram / correction is warranted;
  which scaffold files need changes; whether a NEW module is justified. Map EVERY proposed change to a real
  source URL - no unsourced edits (this is the curriculum's own anti-recursive-drift rule). Skip anything
  already covered. Prefer additive, high-signal updates over churn.

### 3. LEARN (apply updates) - fan out with the Workflow
- Run `Workflow({ scriptPath: "<REPO>/tools/improve-workflow.js", args: { researchPath: "<new raw file>",
  focus: "$ARGUMENTS" } })`. It does gap-analysis -> parallel per-note updates -> audit. For tiny changes
  you may instead Edit notes directly.
- Honor the SPEC house style exactly: YAML frontmatter, `[[NN - ...]]` wikilinks, valid ```mermaid fences
  with italic captions, inline `[name](url)` citations from REAL sources only, " - " not em-dashes,
  a `## Navigation` footer on every note.

### 4. VERIFY (audit + consistency) - the spine, never skip
- Wikilinks: every `[[link]]` resolves to one of the note filenames (or a real heading).
- Mermaid: every fence balanced and starts with a valid diagram keyword.
- Citations: every new URL actually appeared in the research / WebSearch results; zero fabricated links.
- Scaffold: `cd <SCAFFOLD> && python3 -m py_compile $(find . -name '*.py')` exits 0; if `pyproject.toml`
  exists, `pip install -e .` so imports resolve and Pyright is clean.
- Canvas: if a note was added/removed, regenerate `Self-Improving Agents Map.canvas`.
- Cross-component consistency: SPEC + notes + scaffold share the same vocabulary, ports (oMLX `:8000`,
  VibeProxy `:8317`), and the embeddings-stay-local rule. Fix any drift.
- Iterate until green. Do NOT proceed to SHIP on a red audit.

### 5. SHIP (push to GitHub)
- Sync updated notes + canvas -> `<REPO>/curriculum/`, scaffold -> `<REPO>/scaffold/`,
  research -> `<REPO>/research/`. Append a dated `CHANGELOG.md` entry summarizing what improved and the
  driving sources. Bump `updated:` frontmatter dates on changed notes.
- Commit as shaneliuyx / shane_liuyx@hotmail.com (NO AI attribution - user policy) with a conventional
  message, e.g. `docs: refresh curriculum from last-30-days sources (YYYY-MM-DD)`.
- Show the diff to the user, then `git push`. Report what changed and the commit URL.

## Guardrails
- Source every claim; no unsourced edits.
- Additive by default - don't rewrite working notes wholesale.
- Never push a failing VERIFY. Keep the human in the loop on the final push.
