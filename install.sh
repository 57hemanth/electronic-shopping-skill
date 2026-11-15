#!/usr/bin/env bash
# Install the skill by symlinking skills/<name> into each agent's user-level skills folder.
# Symlinks mean a `git pull` updates every agent at once.
#
#   ./install.sh                 # Claude Code + Codex + Gemini CLI
#   ./install.sh --claude        # Claude Code only            (~/.claude/skills)
#   ./install.sh --codex         # Codex                       (~/.agents/skills)
#   ./install.sh --gemini        # Gemini CLI                  (~/.agents/skills + ~/.gemini/commands)
#   ./install.sh --uninstall     # remove our links from every location
#   ./install.sh --list          # show what is installed where
#
# Codex and Gemini CLI both read ~/.agents/skills, so the skill is linked there once. It is not also
# linked into ~/.gemini/skills: Gemini warns about a conflict when the same skill is in both.
# --gemini also links commands/*.toml into ~/.gemini/commands, which adds the /electronic-shopping command.
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
SRC="$REPO/skills"
CMD_SRC="$REPO/commands"
CLAUDE="$HOME/.claude/skills"
AGENTS="$HOME/.agents/skills"
GEMINI_CMDS="$HOME/.gemini/commands"
MODE=install
want_claude=0; want_agents=0; want_gemini_cmds=0

for arg in "$@"; do
  case "$arg" in
    --claude) want_claude=1 ;;
    --codex) want_agents=1 ;;
    --gemini) want_agents=1; want_gemini_cmds=1 ;;
    --uninstall) MODE=uninstall ;;
    --list) MODE=list ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done
if [ $((want_claude + want_agents + want_gemini_cmds)) -eq 0 ] || [ "$MODE" != install ]; then
  want_claude=1; want_agents=1; want_gemini_cmds=1
fi

skills=()
for d in "$SRC"/*/; do [ -f "$d/SKILL.md" ] && skills+=("$(basename "$d")"); done
cmds=()
for f in "$CMD_SRC"/*.toml; do [ -f "$f" ] && cmds+=("$(basename "$f")"); done

link() {  # link <source> <dest>
  if [ -e "$2" ] && [ ! -L "$2" ]; then echo "  skip $2 (a real file or folder exists; not ours)" >&2; return 1; fi
  ln -sfn "$1" "$2"
}

do_dir() {  # do_dir <target dir> <source dir> <names...>
  local t="$1" src="$2"; shift 2
  case "$MODE" in
    install)
      mkdir -p "$t"; local n=0
      for s in "$@"; do link "$src/$s" "$t/$s" && n=$((n + 1)); done
      echo "Linked $n into $t" ;;
    uninstall)
      local n=0
      for s in "$@"; do
        if [ -L "$t/$s" ] && [ "$(readlink "$t/$s")" = "$src/$s" ]; then rm "$t/$s"; n=$((n + 1)); fi
      done
      echo "Removed $n from $t" ;;
    list)
      echo "$t:"
      for s in "$@"; do
        if [ -L "$t/$s" ] && [ "$(readlink "$t/$s")" = "$src/$s" ]; then echo "  ✓ $s"; else echo "  · $s (not installed)"; fi
      done ;;
  esac
}

[ $want_claude -eq 1 ] && do_dir "$CLAUDE" "$SRC" "${skills[@]}"
[ $want_agents -eq 1 ] && do_dir "$AGENTS" "$SRC" "${skills[@]}"
[ $want_gemini_cmds -eq 1 ] && [ ${#cmds[@]} -gt 0 ] && do_dir "$GEMINI_CMDS" "$CMD_SRC" "${cmds[@]}"

if [ "$MODE" = install ]; then
  echo
  echo "Claude Code: start a new session; type /electronic-shopping or just ask."
  echo "Codex:       start a new session; type \$electronic-shopping, run /skills, or just ask."
  echo "Gemini CLI:  start a new session; type /electronic-shopping or just ask (it asks before activating the skill)."
fi
exit 0
