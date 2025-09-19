#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$PWD}"
cd "$PROJECT_ROOT"

# 專案完整性檢查
need_files=( "tools" "db" "reports_auto" )
for f in "${need_files[@]}"; do
  [ -e "$f" ] || { echo "[ERR] not project root: missing $f"; exit 2; }
done

# 啟動 venv（沒有就略過）
if [ -f .venv/bin/activate ]; then
  . .venv/bin/activate
fi

# 設 PYTHONPATH（含 src/）
export PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/src:${PYTHONPATH:-}"

# 可選：本地 KIE 權重（你有就設；沒有就保留空）
: "${KIE_MODEL_DIR:=${KIE_MODEL_DIR:-}}"
# auto-detect KIE model dir (only when empty)
if [ -z "$KIE_MODEL_DIR" ]; then
  for cand in \
    "$PROJECT_ROOT/artifacts_inbox/kie1/model" \
    "$PROJECT_ROOT/artifacts/kie/model" \
    "$PROJECT_ROOT/model" \
    ; do
    if [ -d "$cand" ] && [ -s "$cand/config.json" ]; then
      export KIE_MODEL_DIR="$cand"
      break
    fi
  done
fi


echo "[OK] cwd=$(pwd)"
echo "[OK] PYTHONPATH=$PYTHONPATH"
python - <<'PY'
import sys, os, json
print(json.dumps({
  "python": sys.version,
  "venv": os.environ.get("VIRTUAL_ENV","(no venv)"),
  "KIE_MODEL_DIR": os.environ.get("KIE_MODEL_DIR",""),
}, ensure_ascii=False, indent=2))
PY


# auto-detect KIE model dir (extended with sibling repo)
if [ -z "$KIE_MODEL_DIR" ]; then
  for cand in \
    "$PROJECT_ROOT/artifacts_inbox/kie1/model" \
    "$PROJECT_ROOT/artifacts/kie/model" \
    "$PROJECT_ROOT/model" \
    "$PROJECT_ROOT/../smart-mail-agent_ssot/artifacts_inbox/kie1/model" \
    ; do
    if [ -d "$cand" ] && [ -s "$cand/config.json" ]; then
      export KIE_MODEL_DIR="$cand"
      break
    fi
  done
fi
