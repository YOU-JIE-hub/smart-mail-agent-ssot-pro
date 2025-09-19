#!/usr/bin/env bash
set -Eeuo pipefail
TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/status/PROJECT_AUDIT_${TS}.md"
mkdir -p "reports_auto/status" "reports_auto/logs"
echo "[${TS:9:2}:${TS:11:2}:${TS:13:2}] writing $OUT"
{
  echo "# Project Audit ($TS)"
  echo "## Artifacts"
  for f in model_pipeline.pkl ens_thresholds.json intent_rules_calib_v11c.json kie_runtime_config.json; do
    if [ -f "artifacts_prod/$f" ]; then
      sz=$(stat -c%s "artifacts_prod/$f" 2>/dev/null || wc -c < "artifacts_prod/$f")
      sha=$(P="artifacts_prod/$f" python - <<'PY'
import os, hashlib; p=os.environ["P"]; print(hashlib.sha256(open(p,'rb').read()).hexdigest())
PY
)
      echo "- $f: FOUND (size=${sz} bytes, sha256=${sha})"
    else
      echo "- $f: MISSING"
    fi
  done
  echo "## DB & Logs"
  if [ -f "db/sma.sqlite" ]; then
    echo "- db/sma.sqlite: FOUND"
    echo "- integrity: $(sqlite3 db/sma.sqlite 'PRAGMA integrity_check;')"
  else
    echo "- db/sma.sqlite: MISSING"
  fi
  touch reports_auto/logs/pipeline.ndjson && echo "- pipeline.ndjson: writable OK"
  echo "## Environment"
  echo "- SMA_SMTP_MODE=${SMA_SMTP_MODE:-unset}"
  echo "- SMA_LLM_PROVIDER=${SMA_LLM_PROVIDER:-unset}"
  echo "## KIE Engine"
  if [ -f artifacts_prod/kie_runtime_config.json ]; then
    eng=$(python - <<'PY'
import json,sys;print(json.load(open('artifacts_prod/kie_runtime_config.json','r',encoding='utf-8')).get('engine','regex'))
PY
); echo "- engine=$eng"
  else
    echo "- engine=regex (default)"
  fi
} > "$OUT"
echo "[OK] audit → $OUT"
