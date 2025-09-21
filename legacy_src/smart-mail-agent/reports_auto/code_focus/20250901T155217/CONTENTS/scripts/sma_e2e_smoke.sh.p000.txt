#!/usr/bin/env bash
set -Eeuo pipefail
source .sma_tools/env_guard.sh
[[ "${DEBUG:-0}" == "1" ]] && set -x

EML_DIR="${1:-${EML_DIR:-data/demo_eml}}"
[[ -d "$EML_DIR" ]] || { echo "[INFO] 建立 demo eml 目錄：$EML_DIR"; mkdir -p "$EML_DIR"; }

# 預跑檢查（不阻斷，只提醒）
miss=0
for f in \
  artifacts_prod/model_pipeline.pkl \
  artifacts_prod/ens_thresholds.json \
  artifacts/intent_pro_cal.pkl \
  reports_auto/intent_thresholds.json
do
  [[ -e "$f" ]] || { echo "[WARN] 缺少：$f"; miss=1; }
done
if [[ ! -d "kie" && ! -d "reports_auto/kie/kie" ]]; then
  echo "[WARN] 沒找到 KIE 權重資料夾：kie/ 或 reports_auto/kie/kie/"; miss=1
fi
(( miss == 1 )) && echo "[HINT] 純 smoke 可先用現有 demo；正式展示請把模型放回既定路徑。"

# 執行 E2E（強制先進專案、先進環境）
if [[ ! -x scripts/sma_e2e_mail.sh ]]; then
  echo "[FATAL] 找不到 scripts/sma_e2e_mail.sh"; exit 90
fi
if ! scripts/sma_e2e_mail.sh "$EML_DIR"; then
  rc=$?
  echo "[FATAL] sma_e2e_mail.sh 執行失敗 rc=$rc"
  echo "[HINT] 先跑 ./scripts/sma_doctor.sh 檢查缺檔 / 環境"
  exit $rc
fi

# 尋找輸出根目錄（相容 e2e_mail / e2e_run）
for d in reports_auto/e2e_mail reports_auto/e2e_run; do
  if [[ -d "$d" ]]; then BASE="$d"; break; fi
done
[[ -n "${BASE:-}" ]] || { echo "[FATAL] 找不到 E2E 產出根目錄（reports_auto/e2e_mail 或 reports_auto/e2e_run）"; exit 91; }

LAST="$(ls -1dt "$BASE"/* 2>/dev/null | head -n1 || true)"
[[ -n "$LAST" ]] || { echo "[FATAL] $BASE 下沒有任何 run"; exit 92; }

for f in cases.jsonl actions.jsonl SUMMARY.md; do
  [[ -f "$LAST/$f" ]] || { echo "[FATAL] 缺少輸出 $f at $LAST"; exit 93; }
done

echo "[OK] E2E smoke 成功"
echo "[INFO] SUMMARY: $LAST/SUMMARY.md"
echo "[INFO] RPA OUT: $LAST/rpa_out"
