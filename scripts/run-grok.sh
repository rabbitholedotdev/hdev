#!/bin/bash
# Isolated Grok task: one non-interactive round in its own worktree.
# Optional HDEV_ACCOUNT_WRAPPER injects the current user's grok account env.
# Does not copy logins. No push, no sudo, no extra network flags.
#   usage: scripts/run-grok.sh <prompt.md>
set -o pipefail
if [ $# -lt 1 ] || [ -z "${1:-}" ]; then
  echo "uso: scripts/run-grok.sh <prompt.md>" >&2
  exit 2
fi
HERE=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
MAIN=${HDEV_MAIN:-$HERE}
# worktree in <area>/_wt/<repo>-<branch>; override with HDEV_GROK_WORKTREE
WT=${HDEV_GROK_WORKTREE:-$MAIN/_wt/harness-dev-grok-ci}
BRANCH=${HDEV_GROK_BRANCH:-grok/ci}
PROMPT=$1
GROK=${HDEV_GROK_BIN:-grok}
WRAP=${HDEV_GROK_WRAPPER:-${HDEV_ACCOUNT_WRAPPER:-}}
if [ -n "${HDEV_BIN_DIR:-}" ]; then
  export PATH="$HDEV_BIN_DIR:/usr/local/bin:/usr/bin:/bin"
else
  export PATH="/usr/local/bin:/usr/bin:/bin"
fi
unset XAI_API_KEY GROK_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN
now() { TZ=America/Sao_Paulo date '+%Y-%m-%d %H:%M:%S %Z'; }

if [ -f "$MAIN/docs/WAITING.md" ]; then echo "STOP $(now) docs/WAITING.md presente"; exit 3; fi
[ -f "$PROMPT" ] || { echo "falta o prompt $PROMPT" >&2; exit 2; }
MODEL=$(python3 -c 'import json,sys
try: r=json.load(open(sys.argv[1]))["roles"]["isolated"]
except Exception: r={}
print(r.get("model") or "grok-4.7")' "$MAIN/.hdev/config.json")
if [ ! -d "$WT" ]; then
  if git -C "$MAIN" show-ref --verify --quiet "refs/heads/$BRANCH"; then
    git -C "$MAIN" worktree add "$WT" "$BRANCH" || exit 1
  else
    git -C "$MAIN" worktree add -b "$BRANCH" "$WT" master || exit 1
  fi
fi
cd "$WT" || exit 1
mkdir -p logs
LOG="logs/sessao-grok-$(TZ=America/Sao_Paulo date +%Y-%m-%d-%H%M%S)-america-sao-paulo.log"
[ -n "$WRAP" ] && [ -x "$WRAP" ] || WRAP=
echo "START $(now) model=$MODEL worktree=$WT branch=$(git branch --show-current) base=$(git rev-parse --short HEAD)" | tee -a "$LOG"
$WRAP "$GROK" -m "$MODEL" --cwd "$WT" --prompt-file "$PROMPT" --output-format plain \
  --always-approve --no-subagents --disable-web-search --max-turns 80 \
  --deny 'Bash(git push:*)' --deny 'Bash(git remote:*)' --deny 'Bash(sudo:*)' \
  --deny 'Bash(curl:*)' --deny 'Bash(wget:*)' --deny 'Bash(gh:*)' </dev/null 2>&1 | tee -a "$LOG"
ec=${PIPESTATUS[0]}
echo "END $(now) exit=$ec head=$(git rev-parse --short HEAD)" | tee -a "$LOG"
exit "$ec"
