#!/usr/bin/env bash
# Links every skill in this repo into ~/.claude/skills/ (safe to re-run).
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.claude/skills"
mkdir -p "$DEST"

for skill in "$REPO"/skills/*/; do
  skill="${skill%/}"
  name="$(basename "$skill")"
  target="$DEST/$name"
  if [ -L "$target" ]; then
    ln -sfn "$skill" "$target"
  elif [ -e "$target" ]; then
    backup="$target.bak.$(date +%s)"
    mv "$target" "$backup"
    echo "  backup: $backup"
    ln -s "$skill" "$target"
  else
    ln -s "$skill" "$target"
  fi
  echo "✓ $name"
done
