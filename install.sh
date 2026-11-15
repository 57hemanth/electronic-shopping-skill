#!/usr/bin/env bash
# Install the skills by symlinking each skills/<name> folder into the agent's user-level skills dir.
# Symlinks mean a `git pull` updates every agent at once.
#
#   ./install.sh                 # Claude Code + Codex
#   ./install.sh --claude        # Claude Code only   (~/.claude/skills)
#   ./install.sh --codex         # Codex only         (~/.agents/skills)
#   ./install.sh --gemini        # Gemini CLI         (~/.gemini/skills)  [later phase; experimental]
#   ./install.sh --uninstall     # remove our symlinks from every target
#   ./install.sh --list          # show what is installed where
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
SRC="$REPO/skills"
declare -a TARGETS=()
MODE=install

for arg in "$@"; do
  case "$arg" in
    --claude) TARGETS+=("$HOME/.claude/skills") ;;
    --codex) TARGETS+=("$HOME/.agents/skills") ;;
    --gemini) TARGETS+=("$HOME/.gemini/skills") ;;
    --uninstall) MODE=uninstall ;;
    --list) MODE=list ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done
[ ${#TARGETS[@]} -eq 0 ] && TARGETS=("$HOME/.claude/skills" "$HOME/.agents/skills")
[ "$MODE" != install ] && [ ${#TARGETS[@]} -eq 2 ] && TARGETS+=("$HOME/.gemini/skills")

skills=()
for d in "$SRC"/*/; do [ -f "$d/SKILL.md" ] && skills+=("$(basename "$d")"); done

for t in "${TARGETS[@]}"; do
  case "$MODE" in
    install)
      mkdir -p "$t"
      n=0
      for s in "${skills[@]}"; do
        dest="$t/$s"
        if [ -e "$dest" ] && [ ! -L "$dest" ]; then
          echo "  skip $dest (a real folder exists; not ours)" >&2; continue
        fi
        ln -sfn "$SRC/$s" "$dest"; n=$((n + 1))
      done
      echo "Linked $n skills into $t" ;;
    uninstall)
      n=0
      for s in "${skills[@]}"; do
        dest="$t/$s"
        if [ -L "$dest" ] && [ "$(readlink "$dest")" = "$SRC/$s" ]; then rm "$dest"; n=$((n + 1)); fi
      done
      echo "Removed $n links from $t" ;;
    list)
      echo "$t:"
      for s in "${skills[@]}"; do
        if [ -L "$t/$s" ]; then echo "  ✓ $s"; else echo "  · $s (not installed)"; fi
      done ;;
  esac
done

if [ "$MODE" = install ]; then
  echo
  echo "Claude Code: start a new session; skills load automatically (or type /electronic-shopping)."
  echo "Codex:       start a new session; type \$electronic-shopping or run /skills."
fi
