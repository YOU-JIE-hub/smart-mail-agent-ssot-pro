#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${SMA_ROOT:-$PWD}"; cd "$ROOT"
. .venv_clean/bin/activate
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"

echo "[REGISTER] 解壓 artifacts_inbox/*.zip"
python -m smart_mail_agent.cli.ml_register

echo "[SMOKE] 三模型"
python - <<'PY'
from smart_mail_agent.ml.infer import smoke_all
import json
print(json.dumps(smoke_all(), ensure_ascii=False, indent=2))
PY

echo "[RAG] 建索引"
python - <<'PY'
from smart_mail_agent.cli.rag_build import build_index
import json
print(json.dumps(build_index(), ensure_ascii=False))
PY

echo "[RAG] 查詢（會依 OPENAI_API_KEY 自動切換 Embeddings）"
python -m smart_mail_agent.cli.rag_query "付款條件是什麼？"
