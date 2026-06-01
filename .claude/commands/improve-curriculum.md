---
description: Refresh the "Building Self-Improving Agents" curriculum from the last 30 days of sources, update notes + scaffold, audit consistency, and push to GitHub.
argument-hint: "[optional extra focus, e.g. 'memory systems' or a new subtopic]"
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, Skill, Workflow, WebSearch, AskUserQuestion
---

# /improve-curriculum - self-improving the curriculum

You are running the maintenance loop for the **Building Self-Improving Agents** curriculum.
This applies the curriculum's own ACT -> RECORD -> REFLECT -> LEARN -> VERIFY thesis to itself:
gather fresh evidence, learn what changed, update the material, VERIFY consistency, then ship.

## Resolve paths (STEP 0 - run this FIRST, do not hardcode machine paths)

Paths differ per machine (clone location, vault name, language). Resolve them dynamically
by IDENTITY (git remote, marker files), not by a fixed location. Run this block and export
the three roots before doing anything else; honor `REPO_DIR` / `LAB_DIR` / `VAULT_DIR` env
overrides when set. If any root stays empty, STOP and ask the user for it - never guess.

```bash
# REPO: the git clone whose origin is this curriculum (works wherever it was cloned)
REPO="${REPO_DIR:-}"
[ -z "$REPO" ] && REPO="$(
  find "$HOME" -maxdepth 5 -name Library -prune -o -name node_modules -prune -o \
       -type d -name self-improving-agents-curriculum -print 2>/dev/null | while read -r d; do
    git -C "$d" remote get-url origin 2>/dev/null | grep -qi self-improving-agents-curriculum && { echo "$d"; break; }
  done)"

# SCAFFOLD: the runnable lab, identified by its GOAL.md marker (env LAB_DIR wins)
SCAFFOLD="${LAB_DIR:-}"
[ -z "$SCAFFOLD" ] && SCAFFOLD="$(find "$HOME" -maxdepth 5 -name Library -prune -o \
  -type f -name GOAL.md -path '*self-improving-agent-lab*' -print 2>/dev/null | head -1 | xargs -r dirname)"
[ -z "$SCAFFOLD" ] && [ -d "$HOME/self-improving-agent-lab" ] && SCAFFOLD="$HOME/self-improving-agent-lab"

# CURRICULUM: the installed notes folder (any vault; VAULT_DIR/<vault>/Self-Improving Agents wins)
CURRICULUM=""
[ -n "$VAULT_DIR" ] && [ -d "$VAULT_DIR/Self-Improving Agents" ] && CURRICULUM="$VAULT_DIR/Self-Improving Agents"
[ -z "$CURRICULUM" ] && CURRICULUM="$(find "$HOME" -maxdepth 6 -name Library -prune -o \
  -type d -name 'Self-Improving Agents' -print 2>/dev/null | grep -v '/.git/' | head -1)"

printf 'REPO=%s\nSCAFFOLD=%s\nCURRICULUM=%s\n' "$REPO" "$SCAFFOLD" "$CURRICULUM"
for v in REPO SCAFFOLD CURRICULUM; do
  [ -z "${!v}" ] && echo "!! $v unresolved - ask the user for it before proceeding, do NOT guess." >&2
done
```

Derived from the roots above (do not hardcode):
- SPEC (authoring contract):   `$REPO/tools/curriculum-spec.md`  - READ THIS FIRST (house style, citations, conventions, the full note list, backend facts)
- Refresh script:              `$REPO/tools/refresh-research.sh`  (reproducible last30days engine call)
- Improvement workflow:        `$REPO/tools/improve-workflow.js`  (parallel note updates + audit)
- Research output dir:         last30days saves to `${LAST30DAYS_MEMORY_DIR:-$HOME/Documents/Last30Days}` (read the engine's "Saved output to ..." line; do not assume a path)
- Optional focus argument:     $ARGUMENTS

## Protocol (do EVERY step; keep a human in the loop on the final push)

### 1. GATHER (fresh evidence)
- Invoke the `/last30days` skill for `building self-improving agents` (weave in `$ARGUMENTS` if given).
  If the skill is unavailable in this context, run `bash $REPO/tools/refresh-research.sh "$ARGUMENTS"`
  which writes a raw `*-raw-refresh.md` to the research dir. Read that raw file in full.
- Run 2-3 `WebSearch` supplements for anything new since the last run (papers, Show HN, releases, tools).
- RECORD: copy/save the new findings into `$REPO/research/` with a dated filename.

### 2. REFLECT (gap analysis)
- Read the SPEC and the current 13 notes (`00 - ...` .. `12 - ...`). Read the new research.
- Produce a concrete CHANGE LIST: per note, what new citation / section / diagram / correction is warranted;
  which scaffold files need changes; whether a NEW module is justified. Map EVERY proposed change to a real
  source URL - no unsourced edits (this is the curriculum's own anti-recursive-drift rule). Skip anything
  already covered. Prefer additive, high-signal updates over churn.

### 3. LEARN (apply updates) - fan out with the Workflow
- Run `Workflow({ scriptPath: "$REPO/tools/improve-workflow.js", args: { researchPath: "<new raw file>",
  focus: "$ARGUMENTS" } })`. It does gap-analysis -> parallel per-note updates -> audit. For tiny changes
  you may instead Edit notes directly.
- Honor the SPEC house style exactly: YAML frontmatter, `[[NN - ...]]` wikilinks, valid ```mermaid fences
  with italic captions, inline `[name](url)` citations from REAL sources only, " - " not em-dashes,
  a `## Navigation` footer on every note.

### 4. VERIFY (audit + consistency) - the spine, never skip
- Wikilinks: every `[[link]]` resolves to one of the note filenames (or a real heading).
- Mermaid: every fence balanced and starts with a valid diagram keyword.
- Citations: every new URL actually appeared in the research / WebSearch results; zero fabricated links.
- Scaffold: `cd $SCAFFOLD && python3 -m py_compile $(find . -name '*.py')` exits 0; if `pyproject.toml`
  exists, `pip install -e .` so imports resolve and Pyright is clean.
- Canvas: if a note was added/removed, regenerate `Self-Improving Agents Map.canvas`.
- Cross-component consistency: SPEC + notes + scaffold share the same vocabulary, ports (oMLX `:8000`,
  VibeProxy `:8317`), and the embeddings-stay-local rule. Fix any drift.
- Iterate until green. Do NOT proceed to SHIP on a red audit.

### 5. SHIP (push to GitHub)
- Sync updated notes + canvas -> `$REPO/curriculum/`, scaffold -> `$REPO/scaffold/`,
  research -> `$REPO/research/`. Append a dated `CHANGELOG.md` entry summarizing what improved and the
  driving sources. Bump `updated:` frontmatter dates on changed notes.
- Commit as shaneliuyx / shane_liuyx@hotmail.com (NO AI attribution - user policy) with a conventional
  message, e.g. `docs: refresh curriculum from last-30-days sources (YYYY-MM-DD)`.
- Show the diff to the user, then `git push`. Report what changed and the commit URL.

## Guardrails
- Source every claim; no unsourced edits.
- Additive by default - don't rewrite working notes wholesale.
- Never push a failing VERIFY. Keep the human in the loop on the final push.
