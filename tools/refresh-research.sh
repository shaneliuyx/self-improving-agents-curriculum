#!/usr/bin/env bash
# refresh-research.sh - reproducible "last 30 days" research pull for the
# Building Self-Improving Agents curriculum. This is the DETERMINISTIC retrieval
# core of /improve-curriculum: it runs the last30days engine directly (no model
# needed), so the GATHER step works even headless / in CI.
#
# Usage:  tools/refresh-research.sh ["extra focus terms"]
# Output: writes a raw research markdown to the last30days research dir and
#         echoes the path. The caller (the /improve-curriculum command) reads it.
set -euo pipefail

EXTRA="${1:-}"
TOPIC="building self-improving agents"
[ -n "$EXTRA" ] && TOPIC="$TOPIC $EXTRA"

# last30days v3 engine requires Python 3.12+
PY="$(command -v python3.13 || command -v python3.12 || true)"
if [ -z "$PY" ]; then
  echo "ERROR: need python3.12+ for the last30days engine (found none)." >&2
  exit 1
fi

# Locate the newest cached engine (handles versioned cache dirs).
SKILL_DIR="$(find "$HOME/.claude/plugins/cache/last30days-skill/last30days" \
  -type f -name last30days.py -path '*/scripts/*' 2>/dev/null \
  | sort -V | tail -1 | xargs -I{} dirname {} 2>/dev/null | xargs -I{} dirname {} 2>/dev/null)"
if [ -z "$SKILL_DIR" ] || [ ! -f "$SKILL_DIR/scripts/last30days.py" ]; then
  echo "ERROR: last30days engine not found under ~/.claude/plugins/cache/last30days-skill" >&2
  exit 1
fi

OUT="$HOME/.claude/plugins/data/last30days-last30days-skill/research"
mkdir -p "$OUT"

# Pick up an optional ScrapeCreators key (unlocks TikTok/Instagram/YouTube tiers).
# Reddit/HN/GitHub/Polymarket work without any key.
[ -f "$HOME/.zshrc" ] && source "$HOME/.zshrc" 2>/dev/null || true

# Query plan (we are the planner; engine consumes this via --plan).
PLAN="$(mktemp "${TMPDIR:-/tmp}/sia-plan.XXXXXX")"
trap 'rm -f "$PLAN"' EXIT
cat > "$PLAN" <<'JSON'
{
  "intent": "concept",
  "freshness_mode": "evergreen_ok",
  "cluster_mode": "none",
  "subqueries": [
    {"label":"primary","search_query":"self-improving AI agents","ranking_query":"What are people saying about building self-improving AI agents?","sources":["reddit","x","youtube","tiktok","instagram","hackernews","github"],"weight":1.0},
    {"label":"self-evolving","search_query":"self-evolving agents memory continual learning","ranking_query":"How are developers building agents that learn and self-evolve over time?","sources":["reddit","youtube","hackernews","github"],"weight":0.8},
    {"label":"frameworks","search_query":"self-improving agent framework reinforcement learning research","ranking_query":"Which frameworks and papers enable self-improving agents?","sources":["reddit","hackernews","github"],"weight":0.5}
  ]
}
JSON

echo "[refresh] topic : $TOPIC"
echo "[refresh] python: $PY"
echo "[refresh] engine: $SKILL_DIR/scripts/last30days.py"
echo "[refresh] out    : $OUT"

"$PY" "$SKILL_DIR/scripts/last30days.py" "$TOPIC" \
  --emit=compact \
  --plan "$PLAN" \
  --subreddits="AI_Agents,LocalLLaMA,MachineLearning,LangChain,AgentsOfAI,singularity,ClaudeAI" \
  --save-dir="$OUT" \
  --save-suffix="refresh" || true

RAW="$(ls -t "$OUT"/*-raw-refresh.md 2>/dev/null | head -1 || true)"
if [ -n "$RAW" ]; then
  echo "[refresh] DONE -> $RAW"
else
  echo "[refresh] WARNING: no raw-refresh file produced; check engine output above." >&2
fi
