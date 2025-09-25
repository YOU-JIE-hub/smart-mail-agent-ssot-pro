#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$HOME/projects/smart-mail-agent_ssot}"; cd "$ROOT"
# 只攔：同一個 from 列表同時 import json（不掃 .venv / reports_auto / data / artifacts_inbox）
grep -RIn \
  --include="*.py" --include="*.sh" \
  --exclude-dir=".venv" --exclude-dir="reports_auto" --exclude-dir="data" --exclude-dir="artifacts_inbox" \
  -E 'from[[:space:]]+pathlib[[:space:]]+import[[:space:]]+[^#;\n]*\bjson\b' . \
  && { echo "[GUARD] found bad pathlib+json import"; exit 1; } \
  || echo "[GUARD] ok: no bad pathlib+json imports"
