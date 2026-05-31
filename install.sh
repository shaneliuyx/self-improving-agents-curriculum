#!/usr/bin/env bash
# install.sh - set up the "Building Self-Improving Agents" curriculum + tooling
# on a fresh machine. Idempotent; safe to re-run.
#
# What it installs:
#   1. The /improve-curriculum slash command into ~/.claude/commands
#   2. The runnable scaffold (lab) into ~/self-improving-agent-lab (+ a .venv with deps)
#   3. The curriculum notes + Canvas into an Obsidian vault / folder you choose
#      (interactive prompt; or set VAULT_DIR=... to skip the prompt)
#
# Configure via env vars (all optional - the script prompts for what it needs):
#   CLAUDE_DIR   default: $HOME/.claude
#   LAB_DIR      default: $HOME/self-improving-agent-lab
#   VAULT_DIR    if set, used as the notes target (no prompt). Set to "skip" to skip.
#
# Examples:
#   bash install.sh                                   # interactive
#   VAULT_DIR="$HOME/MyVault" bash install.sh         # non-interactive
#   VAULT_DIR=skip bash install.sh                    # tooling only, no notes
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
LAB_DIR="${LAB_DIR:-$HOME/self-improving-agent-lab}"

c_say(){ printf '\033[36m[install]\033[0m %s\n' "$*"; }
c_ok(){  printf '\033[32m[ok]\033[0m %s\n' "$*"; }
c_warn(){ printf '\033[33m[warn]\033[0m %s\n' "$*"; }

c_say "Repo: $REPO_DIR"

# ---------------------------------------------------------------------------
# 1. Slash command
# ---------------------------------------------------------------------------
c_say "Installing /improve-curriculum -> $CLAUDE_DIR/commands"
mkdir -p "$CLAUDE_DIR/commands"
cp "$REPO_DIR/.claude/commands/improve-curriculum.md" "$CLAUDE_DIR/commands/improve-curriculum.md"
c_ok "slash command installed (run /improve-curriculum in Claude Code)"

# ---------------------------------------------------------------------------
# 2. Runnable scaffold
# ---------------------------------------------------------------------------
c_say "Installing scaffold -> $LAB_DIR"
mkdir -p "$LAB_DIR"
cp -R "$REPO_DIR/scaffold/." "$LAB_DIR/"
chmod +x "$LAB_DIR/scripts/go" "$LAB_DIR/scripts/commit" 2>/dev/null || true
c_ok "scaffold copied"

# ---------------------------------------------------------------------------
# 3. Python deps (venv-first: works on PEP 668 externally-managed Pythons)
# ---------------------------------------------------------------------------
PY="$(command -v python3.13 || command -v python3.12 || command -v python3 || true)"
if [ -n "$PY" ]; then
  if "$PY" -m pip install -e "$LAB_DIR" >/dev/null 2>&1; then
    c_ok "installed deps into $PY (editable)"
  else
    c_warn "System pip is blocked (PEP 668 externally-managed). Creating a venv..."
    if "$PY" -m venv "$LAB_DIR/.venv" && "$LAB_DIR/.venv/bin/pip" install -q -e "$LAB_DIR"; then
      c_ok "deps installed in venv. Activate with: source \"$LAB_DIR/.venv/bin/activate\""
    else
      c_warn "Could not auto-install deps. Run manually:"
      c_warn "  $PY -m venv \"$LAB_DIR/.venv\" && \"$LAB_DIR/.venv/bin/pip\" install -e \"$LAB_DIR\""
    fi
  fi
else
  c_warn "No python3 found. Install Python 3.10+ then: pip install -e \"$LAB_DIR\""
fi
if ! command -v python3.12 >/dev/null 2>&1 && ! command -v python3.13 >/dev/null 2>&1; then
  c_warn "Python 3.12+ not found - the /improve-curriculum research refresh needs it."
fi

# .env
if [ ! -f "$LAB_DIR/.env" ] && [ -f "$LAB_DIR/.env.example" ]; then
  cp "$LAB_DIR/.env.example" "$LAB_DIR/.env"
  c_ok "created $LAB_DIR/.env (edit AGENT_BACKEND=omlx|vibeproxy and model names)"
fi

# ---------------------------------------------------------------------------
# 4. Curriculum notes -> a directory you choose (interactive prompt)
# ---------------------------------------------------------------------------
NOTES_TARGET="${VAULT_DIR:-}"
if [ -z "$NOTES_TARGET" ]; then
  if [ -t 0 ]; then
    echo
    c_say "Where should the 13 curriculum markdown notes + Canvas be stored?"
    echo   "      Enter a path to an Obsidian vault (or any folder)."
    echo   "      A 'Self-Improving Agents' subfolder will be created inside it."
    echo   "      Press Enter to skip installing the notes."
    printf "      Target directory: "
    read -r NOTES_TARGET || NOTES_TARGET=""
  else
    c_warn "Non-interactive run and VAULT_DIR not set - skipping notes install."
    c_warn "Re-run interactively, or: VAULT_DIR=/path/to/vault bash install.sh"
  fi
fi

# normalise: expand a leading ~, treat the sentinel "skip" as skip
NOTES_TARGET="${NOTES_TARGET/#\~/$HOME}"
if [ -n "$NOTES_TARGET" ] && [ "$NOTES_TARGET" != "skip" ]; then
  DEST="$NOTES_TARGET/Self-Improving Agents"
  c_say "Installing notes -> $DEST"
  mkdir -p "$DEST"
  cp "$REPO_DIR"/curriculum/*.md "$DEST/"
  cp "$REPO_DIR"/curriculum/*.canvas "$DEST/" 2>/dev/null || true
  c_ok "13 notes + Canvas installed into: $DEST"
else
  c_warn "Skipped installing notes. To do it later:  VAULT_DIR=/path/to/vault bash install.sh"
fi

# ---------------------------------------------------------------------------
# 5. last30days plugin check (needed by /improve-curriculum GATHER)
# ---------------------------------------------------------------------------
if [ -d "$HOME/.claude/plugins/cache/last30days-skill" ]; then
  c_ok "last30days plugin detected"
else
  c_warn "last30days plugin not found - install it to enable the research-refresh step."
fi

echo
c_ok "Done."
echo "  - In Claude Code:  /improve-curriculum   (refresh + audit + push)"
echo "  - Run the lab:     cd \"$LAB_DIR\" && ./scripts/go"
[ -d "$LAB_DIR/.venv" ] && echo "                     (first: source \"$LAB_DIR/.venv/bin/activate\")"
echo "  - Backends:        start oMLX (:8000) or VibeProxy (:8317); set AGENT_BACKEND in $LAB_DIR/.env"
