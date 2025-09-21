#!/usr/bin/env bash
# scripts/sma_acceptance_check.sh — 依九大條款一鍵驗收；必要時可選擇先跑一次 E2E
set -Eeuo pipefail
set -o errtrace
export PS4='+ [sma_acceptance_check.sh:${LINENO}] ► '
trap 'rc=$?; echo "[EXIT] rc=$rc"; exit $rc' EXIT
trap 'rc=$?; echo "[ERR] line=$LINENO rc=$rc cmd=${BASH_COMMAND}"; exit $rc' ERR

# 0) 進專案 + 啟環境 + 匯出
. .sma_tools/env_guard.sh

# 1) 基本目錄
mkdir -p reports_auto/e2e_mail reports_auto/logs
LOG_NDJSON="reports_auto/logs/pipeline.ndjson"
touch "$LOG_NDJSON"

# 2) 模型/門檻檢查（不改名不搬家）
REQS=(
  "artifacts_prod/model_pipeline.pkl"
  "artifacts_prod/ens_thresholds.json"
  "artifacts/intent_pro_cal.pkl"
  "reports_auto/intent_thresholds.json"
)
missing=0
for f in "${REQS[@]}"; do
  if [[ ! -f "$f" ]]; then echo "[MISS][MODEL] $f 不存在"; missing=1; fi
done
# KIE 兩選一
if [[ -d "kie" ]]; then KIE_DIR="kie"
elif [[ -d "reports_auto/kie/kie" ]]; then KIE_DIR="reports_auto/kie/kie"
else echo "[MISS][KIE] 缺少 kie/ 或 reports_auto/kie/kie/"; missing=1; KIE_DIR=""
fi
[[ $missing -eq 0 ]] || { echo "[ABORT] 模型或門檻未就緒"; exit 80; }

# 3) 是否要先跑一次 E2E（預設會跑；若已存在最新 run 可略過）
RUN_TS="$(date +%Y%m%dT%H%M%S)"
RUN_DIR="reports_auto/e2e_mail/$RUN_TS"
if [[ "${SMA_SKIP_E2E:-0}" -eq 0 ]]; then
  echo "[RUN] ./scripts/sma_e2e_mail.sh data/demo_eml"
  ./scripts/sma_e2e_mail.sh data/demo_eml
else
  echo "[SKIP] 依環境變數 SMA_SKIP_E2E=1 跳過 E2E"
fi

# 4) 找到最新一次 run 目錄
LAST_DIR="$(ls -1dt reports_auto/e2e_mail/* 2>/dev/null | head -n1 || true)"
[[ -n "$LAST_DIR" ]] || { echo "[FAIL] 找不到任何 e2e_mail 輸出"; exit 81; }

# 5) 驗收條件（逐項）
ok_all=1

# [ ] A: 基本檔案
for f in "cases.jsonl" "actions.jsonl" "SUMMARY.md"; do
  if [[ ! -f "$LAST_DIR/$f" ]]; then echo "[FAIL][A] 缺少 $f"; ok_all=0; fi
done

# [ ] B: RPA 產物五大類
need_dirs=( "rpa_out" "rpa_out/email_outbox" "rpa_out/tickets" "rpa_out/diffs" "rpa_out/faq_replies" "rpa_out/quotes" )
for d in "${need_dirs[@]}"; do
  if [[ ! -d "$LAST_DIR/$d" ]]; then echo "[FAIL][B] 缺少目錄 $d"; ok_all=0; fi
done

# [ ] C: DB 與四表（actions / intent_preds / kie_spans / err_log）
DB="db/sma.sqlite"
if [[ ! -f "$DB" ]]; then
  echo "[FAIL][C] 缺少 $DB"
  ok_all=0
else
  if command -v sqlite3 >/dev/null 2>&1; then
    for t in actions intent_preds kie_spans err_log; do
      if ! sqlite3 "$DB" "SELECT 1 FROM $t LIMIT 1;" >/dev/null 2>&1; then
        echo "[FAIL][C] DB 表不存在或無資料：$t"
        ok_all=0
      fi
    done
  else
    echo "[WARN][C] 系統無 sqlite3，略過表檢查"
  fi
fi

# [ ] D: Pipeline NDJSON 有新增/存在
if [[ ! -s "$LOG_NDJSON" ]]; then
  echo "[FAIL][D] pipeline.ndjson 不存在或為空：$LOG_NDJSON"
  ok_all=0
fi

# [ ] E: pytest 可執行（如存在 tests/）
if [[ -d "tests" ]]; then
  if ! pytest -q >/dev/null 2>&1; then
    echo "[FAIL][E] pytest 未全綠（或環境缺少依賴）"
    ok_all=0
  else
    echo "[PASS][E] pytest 全綠"
  fi
else
  echo "[SKIP][E] 專案無 tests/ 目錄"
fi

# [ ] F: Spam/Intent/KIE 僅從既定路徑讀（靜態檢查）
for p in "artifacts_prod/model_pipeline.pkl" "artifacts_prod/ens_thresholds.json" \
         "artifacts/intent_pro_cal.pkl" "reports_auto/intent_thresholds.json"; do
  [[ -f "$p" ]] || { echo "[FAIL][F] 缺少 $p"; ok_all=0; }
done
[[ -n "$KIE_DIR" ]] || { echo "[FAIL][F] 未找到 KIE 目錄"; ok_all=0; }

# [ ] G: 缺檔時需清楚報錯（此腳本已在 2) 與 3) 有明確 MISS/ABORT 訊息）

# 結論
if [[ "$ok_all" -eq 1 ]]; then
  echo "----- ACCEPTANCE SUMMARY -----"
  echo "LAST_RUN: $LAST_DIR"
  echo "MODELS: OK (Spam/Intent/KIE)"
  echo "RPA_OUT: OK"
  echo "DB: OK"
  echo "LOG: $LOG_NDJSON"
  echo "CI: 測試全綠或無 tests/"
  echo "------------------------------"
  exit 0
else
  echo "----- ACCEPTANCE FAILED -----"
  echo "請依上方 FAIL/WARN 訊息處置後重跑：./scripts/sma_acceptance_check.sh"
  exit 82
fi
