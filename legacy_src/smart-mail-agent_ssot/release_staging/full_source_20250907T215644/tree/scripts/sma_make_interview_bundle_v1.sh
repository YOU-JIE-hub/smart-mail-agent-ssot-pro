#!/usr/bin/env bash
set -euo pipefail
ROOT="$(pwd)"
TS="$(date +%Y%m%dT%H%M%S)"
OUT="release_staging/interview_${TS}"
PUB="${OUT}/bundle"
mkdir -p "${PUB}"

# 1) 先確保你有最新遮罩與分數板
bash scripts/sma_dump_all_data_masked_v2.sh

# 2) 收集必要檔（小體積、可 demo）
LATEST_DUMP="$(ls -td reports_auto/final_dump/*/ | head -n1)"
mkdir -p "${PUB}/data_masked" "${PUB}/scripts" "${PUB}/docs" "${PUB}/artifacts_prod"

# 遮罩資料
cp -f "${LATEST_DUMP}/intent/intent_dataset_masked.jsonl" "${PUB}/data_masked/" || true
cp -f "${LATEST_DUMP}/intent/intent_dataset_masked.csv"   "${PUB}/data_masked/" || true
cp -f "${LATEST_DUMP}/kie/gold_merged_mask_fixed.jsonl"   "${PUB}/data_masked/" || true
cp -f "${LATEST_DUMP}/spam/text_predictions_test_masked.tsv" "${PUB}/data_masked/" || true
[ -f "${LATEST_DUMP}/SCORECARD_latest.md" ] && cp -f "${LATEST_DUMP}/SCORECARD_latest.md" "${PUB}/docs/"

# 校準與門檻（可公開）
cp -f artifacts_prod/ens_thresholds.json "${PUB}/artifacts_prod/" 2>/dev/null || true
cp -f artifacts_prod/intent_rules_calib_v11c.json "${PUB}/artifacts_prod/" 2>/dev/null || true

# 3) 放入 Demo 執行器（E2E）
cp -f scripts/sma_e2e_mail.sh "${PUB}/scripts/" 2>/dev/null || true
cp -f scripts/e2e_mail_runner.py "${PUB}/scripts/" 2>/dev/null || true

# 4) 產 README（面試說明）
cat > "${PUB}/README_INTERVIEW.md" <<'EOF'
# Smart Mail Agent — Interview Bundle

## 你可以直接講的一句話
> 把進來的郵件自動「讀懂 → 判斷 → 執行」，把能自動化的工作全做掉，並且可審計、可回放。

## 怎麼 Demo
1. 安裝 Python 3.10+，啟 venv，`pip install -r requirements.txt`（如需）。
2. 準備 `.eml` 放在 `demo_eml/`（也可用 `data_masked/intent_dataset_masked.jsonl` 直接跑）。
3. 執行：`bash scripts/sma_e2e_mail.sh demo_eml`  
   輸出位於 `reports_auto/e2e_mail/<timestamp>/`：
   - `SUMMARY.md`：Spam/Intent/Actions 統計
   - `rpa_out/`：`email_outbox/`、`tickets/`、`diffs/`、`faq_replies/`、`quotes/`
   - `db/sma.sqlite` 與 `reports_auto/logs/pipeline.ndjson` 可審計、可回放

## 指標（SCORECARD 摘要）
- Intent (v11c, cleaned): micro/macro F1 約 0.733 / 0.670  
- KIE (hybrid v4): strict micro F1 ≈ 0.800（SLA 維持 HIL）  
- Spam (auto-cal v4): AUC ≈ 0.992；最佳閾值 F1 ≈ 0.948  

## 結構
- `data_masked/`：遮罩資料（可公開）
- `artifacts_prod/`：門檻/校準（可公開）
- `scripts/`：`sma_e2e_mail.sh` + `e2e_mail_runner.py`
- `docs/SCORECARD_latest.md`：整體指標
EOF

# 5) 產壓縮檔
TARBALL="release_staging/interview_bundle_${TS}.tar.gz"
tar -czf "${TARBALL}" -C "${OUT}" "bundle"
echo "[OK] interview bundle => ${TARBALL}"
