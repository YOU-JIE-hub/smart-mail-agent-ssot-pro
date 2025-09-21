#!/usr/bin/env bash
set -Eeuo pipefail
OLD_DIR="${1:-}"
[[ -z "$OLD_DIR" ]] && { echo "用法: scripts/old_vs_new_audit.sh /path/to/old_repo_root" >&2; exit 2; }
TS="$(date +%Y%m%dT%H%M%S)"; OUT="reports_auto/status/DIFF_${TS}.md"; mkdir -p reports_auto/status
echo "# Diff Report @ ${TS}" > "$OUT"
echo -e "\n## 新專案已覆蓋的功能模組" >> "$OUT"
for pat in "src/smart_mail_agent/actions" "src/smart_mail_agent/cli" "src/smart_mail_agent/rag" "scripts" "reports_auto"; do
  echo "- [$pat] 存在: $( [ -e "$pat" ] && echo YES || echo NO )" >> "$OUT"
done
echo -e "\n## 舊專案核心檔案（僅列路徑，不讀內容）" >> "$OUT"
find "$OLD_DIR" -maxdepth 2 -type f | head -n 200 >> "$OUT" || true
echo -e "\n> 提示：把需要 1:1 移植的檔名/資料夾貼進來，我幫你補上對應 CLI/模組骨架。" >> "$OUT"
echo "[DIFF] $OUT"
