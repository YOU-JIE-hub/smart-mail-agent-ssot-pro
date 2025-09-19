#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
OUT_DIR="reports_auto/pack_out"; mkdir -p "$OUT_DIR"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
PAY="$TMP/payload"; mkdir -p "$PAY"

# ====== 你要收的完整代碼 / 設定 / 報告 ======
INCLUDE_PATTERNS=(
  "src/**/*"                          # 全部源碼
  "intent/**/*.py"                    # 意圖模組源碼
  "scripts/*.sh" "scripts/http_api_min.py" "scripts/env.default" "Makefile"
  "vendor/sma_tools/**/*.py"
  "data/intent_eval/*.jsonl"
  "reports_auto/status/INTENTS_SUMMARY_*.md"
)

# ====== 所有「已知大檔」：只做 pointer + 在 MANIFEST 列出絕對路徑 ======
DECLARED_PATHS=(
  "/home/youjie/projects/smart-mail-agent-ssot-pro/intent/intent/artifacts/intent_pro_cal.pkl"
  "/home/youjie/projects/smart-mail-agent-ssot-pro/intent/intent/.sma_tools/runtime_threshold_router.py"
  "/home/youjie/projects/smart-mail-agent_ssot/.sma_tools/runtime_threshold_router.py"
  "/home/youjie/projects/smart-mail-agent-ssot-pro/data/intent_eval/dataset.cleaned.jsonl"
  "/home/youjie/projects/smart-mail-agent_ssot/data/kie_eval/gold_merged.jsonl"
  "/home/youjie/projects/smart-mail-agent_ssot/data/kie/test_real.for_eval.jsonl"
  "/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/77/77/artifacts_sa/spam_rules_lr.pkl"
)

MAX=$((256*1024*1024))  # 256MB

add_file(){ # $1: src file；存在即加入，>256MB 轉 pointer
  local f="$1"; [ -f "$f" ] || return 0
  local rel="$f"; local dst="$PAY/$rel"
  mkdir -p "$(dirname "$dst")"
  local sz; sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
  if [ "$sz" -gt "$MAX" ]; then
    cat > "${dst}.pointer" <<EOF
# POINTER (size > 256MB)
SOURCE_ABS=$(cd "$(dirname "$f")" && pwd)/$(basename "$f")
SIZE_BYTES=$sz
NOTE=Too large for chat upload. Keep this local and use SOURCE_ABS.
EOF
  else
    cp -f "$f" "$dst"
  fi
}

# 展開 patterns（支援 **）
bash -lc '
  shopt -s globstar nullglob
  for pat in "${INCLUDE_PATTERNS[@]}"; do
    for f in $pat; do printf "%s\0" "$f"; done
  done
' > "$TMP/inc.zlist"

# 寫入檔案
while IFS= read -r -d '' f; do add_file "$f"; done < "$TMP/inc.zlist"

# MANIFEST：列出所有模型/資料絕對路徑（含雜湊若 <=256MB）
MAN="$PAY/MANIFEST.txt"
{
  echo "# MANIFEST (generated $(date -Is))"
  echo "ROOT=$(pwd)"
  echo
  echo "## INCLUDED PATTERNS:"; for p in "${INCLUDE_PATTERNS[@]}"; do echo "- $p"; done
  echo
  echo "## DECLARED MODELS & DATA (absolute paths):"
  for p in "${DECLARED_PATHS[@]}"; do
    if [ -e "$p" ]; then
      sz=$(stat -c%s "$p" 2>/dev/null || echo 0)
      if [ "$sz" -le "$MAX" ] && command -v sha256sum >/dev/null 2>&1; then
        h="$(sha256sum "$p" | awk '{print $1}')"
        echo "- $p  (size=${sz}, sha256=${h})"
      else
        echo "- $p  (size=${sz})"
      fi
      add_file "$p"   # 也同步 pointer/檔案到 payload
    else
      echo "- $p  (MISSING)"
    fi
  done
} > "$MAN"

# 產出策略：最多 10 檔；超過自動收斂成單一 tar.gz
mapfile -d '' LIST < <(cd "$PAY" && find . -type f -print0)
COUNT="${#LIST[@]}"; STAMP="$(date +%Y%m%dT%H%M%S)"
if [ "$COUNT" -gt 10 ]; then
  ART="$OUT_DIR/project_payload_${STAMP}.tar.gz"
  tar -C "$PAY" -czf "$ART" .
  echo "$ART"
else
  PK="$OUT_DIR/project_payload_${STAMP}"
  mkdir -p "$PK"
  cp -a "$PAY/." "$PK/"
  (cd "$PK" && find . -type f | sed "s|^.|$PK|")
  echo "$PK"
fi
