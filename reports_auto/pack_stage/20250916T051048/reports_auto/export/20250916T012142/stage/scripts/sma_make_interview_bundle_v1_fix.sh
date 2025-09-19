#!/usr/bin/env bash
set -euo pipefail
set -o pipefail
TRACE="${TRACE:-1}"           # TRACE=1 顯示詳細步驟
TIMEOUT_SEC="${TIMEOUT_SEC:-600}"  # 遮罩產出最多等 10 分鐘
ROOT="$(pwd)"
TS="$(date +%Y%m%dT%H%M%S)"
OUT="release_staging/interview_${TS}"
PUB="${OUT}/bundle"
mkdir -p "${PUB}"
log(){ echo "[$(date +%H:%M:%S)] $*"; }

if [ "${TRACE}" = "1" ]; then set -x; fi

log "[STEP 0] 先確保最新遮罩資料與 SCORECARD（加超時）"
if command -v timeout >/dev/null 2>&1; then
  timeout "${TIMEOUT_SEC}" bash scripts/sma_dump_all_data_masked_v2.sh
else
  bash scripts/sma_dump_all_data_masked_v2.sh
fi

LATEST_DUMP="$(ls -td reports_auto/final_dump/*/ 2>/dev/null | head -n1 || true)"
if [ -z "${LATEST_DUMP:-}" ]; then
  echo "[FATAL] 找不到 reports_auto/final_dump/*/，遮罩資料產出失敗"; exit 2
fi
log "[OK] latest dump => ${LATEST_DUMP}"

log "[STEP 1] 準備面試捆包目錄"
mkdir -p "${PUB}/data_masked" "${PUB}/scripts" "${PUB}/docs" "${PUB}/artifacts_prod"

log "[STEP 2] 拷貝必要遮罩資料（可公開）"
cp -f "${LATEST_DUMP}/intent/intent_dataset_masked.jsonl"        "${PUB}/data_masked/" || true
cp -f "${LATEST_DUMP}/intent/intent_dataset_masked.csv"          "${PUB}/data_masked/" || true
cp -f "${LATEST_DUMP}/kie/gold_merged_mask_fixed.jsonl"          "${PUB}/data_masked/" || true
cp -f "${LATEST_DUMP}/spam/text_predictions_test_masked.tsv"     "${PUB}/data_masked/" || true
[ -f "${LATEST_DUMP}/SCORECARD_latest.md" ] && cp -f "${LATEST_DUMP}/SCORECARD_latest.md" "${PUB}/docs/"

log "[STEP 3] 校準/門檻（可公開）"
cp -f artifacts_prod/ens_thresholds.json            "${PUB}/artifacts_prod/" 2>/dev/null || true
cp -f artifacts_prod/intent_rules_calib_v11c.json   "${PUB}/artifacts_prod/" 2>/dev/null || true

log "[STEP 4] 放入 E2E Demo 執行器（若缺就略過不報錯）"
cp -f scripts/sma_e2e_mail.sh     "${PUB}/scripts/" 2>/dev/null || true
cp -f scripts/e2e_mail_runner.py  "${PUB}/scripts/" 2>/dev/null || true

log "[STEP 5] 產 README（面試說明）"
cat > "${PUB}/README_INTERVIEW.md" <<'EOF'
# Smart Mail Agent — Interview Bundle
> 把進來的郵件自動「讀懂 → 判斷 → 執行」，把能自動化的工作全做掉，並且可審計、可回放。

## Demo
1) 準備 Python 3.10+、venv；2) 放幾封 .eml 到 demo_eml/；3) `bash scripts/sma_e2e_mail.sh demo_eml`
輸出：reports_auto/e2e_mail/<ts>/（SUMMARY.md、rpa_out/*、db/sma.sqlite、logs/pipeline.ndjson）

## 指標（概要）
- Intent (v11c): micro/macro F1 ≈ 0.733 / 0.670
- KIE (hybrid v4): strict micro F1 ≈ 0.800（SLA 欄位 HIL）
- Spam: ROC-AUC ≈ 0.992，最佳 F1 ≈ 0.948

## 結構
- data_masked/  遮罩資料
- artifacts_prod/ 門檻/校準
- scripts/      一鍵 E2E
- docs/SCORECARD_latest.md  指標
EOF

log "[STEP 6] 產出 MANIFEST（快速檢視內容與 SHA256）"
MAN="${OUT}/MANIFEST_INTERVIEW.md"
{
  echo "# Interview Bundle Manifest (${TS})"
  echo
  echo "| file | bytes | sha256 |"
  echo "|---|---:|---|"
  while IFS= read -r f; do
    [ -f "$f" ] || continue
    sz=$(stat -c%s "$f"); sha=$(sha256sum "$f" | awk '{print $1}')
    echo "| \`$f\` | ${sz} | \`${sha}\` |"
  done < <(find "${PUB}" -type f | sort)
} > "${MAN}"

log "[STEP 7] 打包"
TARBALL="release_staging/interview_bundle_${TS}.tar.gz"
tar -czf "${TARBALL}" -C "${OUT}" "bundle"

set +x
log "[DONE] interview bundle => ${TARBALL}"
log "Quick peek:"
echo "  - $(du -h "${TARBALL}" | awk '{print $1}')  ${TARBALL}"
echo "  - MANIFEST: ${MAN}"
