#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
TS="$(date +%Y%m%dT%H%M%S)"
PRO="$ROOT/reports_auto/pro/latest"
ONL="$ROOT/reports_auto/online/latest"
STAT_DIR="$ROOT/reports_auto/status"
ENV_MD="$(ls -t "$STAT_DIR"/ENV_DOCTOR_*.md 2>/dev/null | head -n1 || true)"
ENV_JSON="$(ls -t "$STAT_DIR"/ENV_DOCTOR_*.json 2>/dev/null | head -n1 || true)"

# 檢查輸入是否存在
[ -d "$PRO" ] || { echo "[FATAL] missing $PRO"; exit 1; }
[ -d "$ONL" ] || { echo "[FATAL] missing $ONL"; exit 1; }

# 臨時佈局
TMP="$ROOT/reports_auto/bundle_tmp_${TS}"
OUT="$ROOT/bundle_${TS}.zip"
rm -rf "$TMP"; mkdir -p "$TMP"/{pro,online,status}

# 收集產物（不含巨大 body，可選擇保留）
rsync -a --delete "$PRO/" "$TMP/pro/"
rsync -a --delete "$ONL/" "$TMP/online/"
# 也把 code/hdr 之外的 body 留著，審核更完整；若要瘦身，可改為 --exclude='*.body'
# rsync -a --delete --exclude='*.body' "$ONL/" "$TMP/online/"

# 加入 Env Doctor 報告
[ -f "$ENV_MD" ]   && cp -a "$ENV_MD"   "$TMP/status/"
[ -f "$ENV_JSON" ] && cp -a "$ENV_JSON" "$TMP/status/"

# 版本與重現說明
cat > "$TMP/README_BUNDLE.txt" <<TXT
Bundle TS: $TS
Reproduce (5 min):
  1) make online && make summary
  2) make doctor
  3) make pro-all
Artifacts inside:
  - pro/: summary.json, summary.md, confusion_matrix.tsv, errors_top.tsv, threshold_sweep.tsv
  - online/: *.code/*.hdr/*.body, run.log
  - status/: ENV_DOCTOR_*.{md,json}
TXT

# 打包 + 校驗
( cd "$TMP" && zip -qr "$OUT" . )
sha256sum "$OUT" > "$ROOT/SHA256SUMS"
echo "BUNDLE_OUT: $OUT"
echo "SHA256SUMS: $ROOT/SHA256SUMS"
rm -rf "$TMP"
