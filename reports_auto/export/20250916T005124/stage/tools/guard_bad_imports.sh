#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$HOME/projects/smart-mail-agent-ssot-pro}"
cd "$ROOT"
bad=0
while IFS= read -r -d '' f; do
  if grep -nE '^[[:space:]]*from[[:space:]]+pathlib[[:space:]]+import[[:space:]][^#;\n]*\bjson\b' "$f" >/dev/null 2>&1; then
    echo "[GUARD] bad import in: $f"; bad=1
  fi
done < <(find . -type f \( -name '*.py' -o -name '*.sh' \) \
  -not -path './.venv/*' -not -path './reports_auto/*' -not -path './data/*' \
  -not -name '*.bak*' -print0)
[ "$bad" -eq 0 ] && echo "[GUARD] ok" || exit 1
