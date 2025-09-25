#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true

TS="$(date +%Y%m%dT%H%M%S)"
OUT="chat_context/${TS}"
mkdir -p "$OUT"

echo "[STEP 0] 確保有最新封裝（public/private）與環境快照"
# 先做最新 final_dump & release_staging（會非常小）
bash scripts/sma_stage_release_materials_v1.sh
bash scripts/sma_freeze_env_v1.sh || true

STAGE="$(ls -td release_staging/*/ | head -n1)"
PUB_TAR="release_staging/public_bundle_$(basename "$STAGE").tar.gz"
PRI_TAR="release_staging/private_bundle_$(basename "$STAGE").tar.gz"
SCORECARD="$(ls -t reports_auto/status/SCORECARD_*.md 2>/dev/null | head -n1 || true)"
ENV_SNAP="$(ls -t artifacts_prod/env_snapshot_*.txt 2>/dev/null | head -n1 || true)"

echo "[STEP 1] 收集最小必要資訊到 ${OUT}"
# 1. 專案導覽
command -v tree >/dev/null 2>&1 && tree -a -L 3 > "${OUT}/tree_L3.txt" \
  || { echo "[INFO] no tree, using find"; find . -maxdepth 3 -print | sed 's#^\./##' > "${OUT}/tree_L3.txt"; }

git status -sb > "${OUT}/git_status.txt" 2>/dev/null || true
git log --oneline -n 30 > "${OUT}/git_log_30.txt" 2>/dev/null || true

# 2. 指標與報告（用最新 scorecard + 三模型報告）
mkdir -p "${OUT}/reports"
if [ -n "$SCORECARD" ] && [ -f "$SCORECARD" ]; then
  cp -f "$SCORECARD" "${OUT}/reports/SCORECARD_latest.md"
fi
# 拷貝三模型最新報告（若存在）
cp -f $(ls -t reports_auto/eval/*/metrics_intent_rules_hotfix_v11*.md 2>/dev/null | head -n1) "${OUT}/reports/" 2>/dev/null || true
cp -f $(ls -t reports_auto/kie_eval/*/metrics_kie_spans.md 2>/dev/null | head -n1)       "${OUT}/reports/" 2>/dev/null || true
cp -f $(ls -t reports_auto/eval/*/metrics_spam_autocal_v4.md 2>/dev/null | head -n1)     "${OUT}/reports/" 2>/dev/null || true

# 3. 校準/門檻與模型小型工件（都很小）
mkdir -p "${OUT}/artifacts_prod"
cp -f artifacts_prod/ens_thresholds.json                "${OUT}/artifacts_prod/" 2>/dev/null || true
cp -f artifacts_prod/intent_rules_calib_v11c.json       "${OUT}/artifacts_prod/" 2>/dev/null || true
cp -f artifacts_prod/model_meta.json                    "${OUT}/artifacts_prod/" 2>/dev/null || true

# 4. 公開/私有可復現封裝（小尺寸的 tar.gz）
mkdir -p "${OUT}/release_staging"
[ -f "$PUB_TAR" ] && cp -f "$PUB_TAR" "${OUT}/release_staging/"
[ -f "$PRI_TAR" ] && cp -f "$PRI_TAR" "${OUT}/release_staging/"

# 5. 環境快照
[ -n "$ENV_SNAP" ] && cp -f "$ENV_SNAP" "${OUT}/"

# 6. 生成最小上下文說明（可給新對話當 README）
cat > "${OUT}/CONTEXT_README.md" <<'MD'
# Chat Context Pack（最小可分享包）

這個 zip 旨在讓新對話快速理解與復現目前專案狀態，而不攜帶大型資料：
- `reports/`：最新總分數板與三模型報告
- `artifacts_prod/`：可公開校準＆門檻與小型中繼資料
- `release_staging/`：public/private 兩個小型封裝（含遮罩公開資料與私有復現材料）
- `env_snapshot_*.txt`：目前環境凍結
- `tree_L3.txt`、`git_status.txt`、`git_log_30.txt`：專案導覽與版本脈絡

> 在新機器上，若要完整復現：先解壓後執行 `scripts/sma_recover_private_pack_v1.sh`（內有 private bundle），或將 `private_bundle_*.tar.gz` 解壓覆蓋到標準路徑後執行 `bash scripts/sma_oneclick_eval_all_pro.sh`。
MD

# 7. 簡單敏感字掃描摘要（結果只存一份 txt；內容不會外傳）
grep -RInE "(AKIA|AIza|sk-[A-Za-z0-9]{20,}|-----BEGIN (RSA|OPENSSH) PRIVATE KEY-----)" \
  --exclude-dir=.git --exclude-dir=.venv --exclude=*.tar.gz --exclude=*.zip --exclude=*.pyc . \
  > "${OUT}/secret_scan_summary.txt" || true

echo "[STEP 2] 壓成單一可分享壓縮檔"
ZIP="chat_context_bundle_${TS}.zip"
rm -f "$ZIP"
( cd "chat_context/${TS}" && zip -rq9 "../../${ZIP}" . )
echo "[OK] bundle => ${ZIP}"
du -h "${ZIP}" | awk '{print "[SIZE] " $0}'

echo
echo "=== 下一步 ==="
echo "在新對話直接上傳： ${ZIP}"
echo "或最小貼文：cat chat_context/${TS}/CONTEXT_README.md"
