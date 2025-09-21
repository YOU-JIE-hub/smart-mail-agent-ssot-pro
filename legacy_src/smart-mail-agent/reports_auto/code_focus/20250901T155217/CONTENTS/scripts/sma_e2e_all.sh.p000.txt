#!/usr/bin/env bash
source .sma_tools/env_guard.sh
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/.sma_tools/env_guard.sh"

STAMP="$(date +%Y%m%d-%H%M%S)"
OUTDIR="reports_auto/e2e_run/${STAMP}"
mkdir -p "${OUTDIR}" "${OUTDIR}/logs" samples/kie

# 權重檢查
test -f artifacts_prod/model_pipeline.pkl   || { echo "[FATAL] 缺 spam 權重 artifacts_prod/model_pipeline.pkl"; exit 91; }
test -f artifacts_prod/ens_thresholds.json  || { echo "[FATAL] 缺 spam 門檻 artifacts_prod/ens_thresholds.json"; exit 92; }
test -f artifacts/intent_pro_cal.pkl        || { echo "[FATAL] 缺 intent 權重 artifacts/intent_pro_cal.pkl"; exit 93; }
test -f reports_auto/intent_thresholds.json || { echo "[FATAL] 缺 intent 門檻 reports_auto/intent_thresholds.json"; exit 94; }

# KIE 權重自動偵測：優先 kie/，退回 reports_auto/kie/kie/
KIE_DIR=""
for d in "kie" "reports_auto/kie/kie"; do
  if [[ -f "$d/model.safetensors" || -f "$d/pytorch_model.bin" ]]; then KIE_DIR="$d"; break; fi
done
[[ -z "$KIE_DIR" ]] && { echo "[FATAL] 找不到 KIE 權重（kie/ 或 reports_auto/kie/kie/）"; exit 95; }

# 播種最小測資（若沒有）
if [[ ! -f data/intent/external_realistic_test.clean.jsonl ]]; then
python - <<'PY'
from pathlib import Path; import json
p=Path("data/intent/external_realistic_test.clean.jsonl"); p.parent.mkdir(parents=True, exist_ok=True)
rows=[
 {"id":"i1","subject":"Need a quote","body":"Please send biz quote for 20 units","label":"biz_quote"},
 {"id":"i2","subject":"Cannot login","body":"Tech support required","label":"tech_support"},
 {"id":"i3","subject":"Complaint","body":"Service was delayed","label":"complaint"},
 {"id":"i4","subject":"Policy question","body":"What is the refund policy?","label":"policy_qa"},
 {"id":"i5","subject":"Profile","body":"Please update my address","label":"profile_update"},
 {"id":"i6","subject":"Other","body":"Just saying hi","label":"other"}
]
with open(p,"w",encoding="utf-8") as w:
    for r in rows: w.write(json.dumps(r,ensure_ascii=False)+"\n")
print("[SEEDED]", p, "N=", len(rows))
PY
fi

# 一鍵跑整體（以 Intent 驗收集作為統一案例清單）
python scripts/sma_e2e_run.py \
  --cases data/intent/external_realistic_test.clean.jsonl \
  --kie_dir "$KIE_DIR" \
  --out_dir "$OUTDIR" \
  2>&1 | tee "${OUTDIR}/logs/e2e_run.log"

echo "[OK] E2E -> $OUTDIR"
