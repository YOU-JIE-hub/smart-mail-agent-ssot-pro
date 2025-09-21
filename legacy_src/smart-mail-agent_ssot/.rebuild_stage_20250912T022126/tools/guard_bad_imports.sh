#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$HOME/projects/smart-mail-agent_ssot}"
cd "$ROOT"

# 只掃程式碼檔，排除虛擬環境、報表/日誌、外來樣本與備份
mapfile -d '' FILES < <(find . -type f \( -name '*.py' -o -name '*.sh' \) \
  -not -path './.venv/*' \
  -not -path './reports_auto/*' \
  -not -path './artifacts_inbox/*' \
  -not -path './data/*' \
  -not -name '*.bak*' -print0)

if (( ${#FILES[@]} == 0 )); then
  echo "[GUARD] ok: no code files to scan"
  exit 0
fi

# 只在「同一個 from … import 名單」中抓到 json 才算違規
# 允許 `from pathlib import Path; import json`（分號是另一個 statement）
pattern='^[[:space:]]*from[[:space:]]+pathlib[[:space:]]+import[[:space:]]+[^#;\n]*\bjson\b'

bad=$(grep -nE "$pattern" "${FILES[@]}" || true)
if [[ -n "$bad" ]]; then
  echo "[GUARD] found bad pathlib+json imports:"
  echo "$bad"
  exit 1
fi
echo "[GUARD] ok: no bad pathlib+json imports"
