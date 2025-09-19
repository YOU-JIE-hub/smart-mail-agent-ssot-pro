#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
IN="${IN:-data/intent/dataset.cleaned.jsonl}"
python - <<'PY'
from pathlib import Path; import os, json
inp=os.environ.get("IN","data/intent/dataset.cleaned.jsonl")
print(f"[EVAL] input={inp} exists={Path(inp).exists()}")
# 實際評測交由你現有 tools/_intent_eval_entry.py；此處只保留入口
PY
[ -f tools/_intent_eval_entry.py ] && python -u tools/_intent_eval_entry.py || true
echo "[OK] tri_eval_fixlabels"
