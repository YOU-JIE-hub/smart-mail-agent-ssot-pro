#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
OUT_DIR="reports_auto/pack_out"; mkdir -p "$OUT_DIR"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
PAY="$TMP/payload"; mkdir -p "$PAY"

# 你要求的收打內容（可再加 pattern，不存在就略過）
INCLUDE_PATTERNS=(
  "scripts/*.sh"
  "scripts/http_api_min.py"
  "vendor/sma_tools/**/*.py"
  "data/intent_eval/*.jsonl"
  "reports_auto/status/INTENTS_SUMMARY_*.md"
  "Makefile"
)

# 你要求：模型/資料集位置要以「絕對路徑」列出（超大檔造成上傳困難→用同名 .pointer）
DECLARED_PATHS=(
  "/home/youjie/projects/smart-mail-agent-ssot-pro/intent/intent/artifacts/intent_pro_cal.pkl"
  "/home/youjie/projects/smart-mail-agent-ssot-pro/intent/intent/.sma_tools/runtime_threshold_router.py"
  "/home/youjie/projects/smart-mail-agent_ssot/.sma_tools/runtime_threshold_router.py"
  "/home/youjie/projects/smart-mail-agent-ssot-pro/data/intent_eval/dataset.cleaned.jsonl"
  # 其他你先前提過的（如果存在就會寫 pointer）：
  "/home/youjie/projects/smart-mail-agent_ssot/data/kie_eval/gold_merged.jsonl"
  "/home/youjie/projects/smart-mail-agent_ssot/data/kie/test_real.for_eval.jsonl"
  "/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/77/77/artifacts_sa/spam_rules_lr.pkl"
)

MAX=$((256*1024*1024))  # 256MB

add_file(){ # $1: src file
  local f="$1"; [ -f "$f" ] || return 0
  local rel="$f"; local dst="$PAY/$rel"
  mkdir -p "$(dirname "$dst")"
  local sz; sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
  if [ "$sz" -gt "$MAX" ]; then
    # 大檔→pointer（同名加 .pointer）
    cat > "${dst}.pointer" <<EOF
# POINTER (size > 256MB)
SOURCE_ABS=$(cd "$(dirname "$f")" && pwd)/$(basename "$f")
SIZE_BYTES=$sz
NOTE=File is too large to upload in chat; keep local and use the absolute path above.
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
' > "$TMP/files.zlist"

# 加入檔案
while IFS= read -r -d '' f; do add_file "$f"; done < "$TMP/files.zlist"

# 輸出 MANIFEST：列出所有指標資料（絕對路徑 + sha256 若檔案可讀且 <=256MB）
MAN="$PAY/MANIFEST.txt"
{
  echo "# MANIFEST for smart-mail-agent-ssot-pro (generated $(date -Is))"
  echo "ROOT=$(pwd)"
  echo
  echo "## INCLUDED PATTERNS:"; for p in "${INCLUDE_PATTERNS[@]}"; do echo "- $p"; done
  echo
  echo "## DECLARED MODELS & DATA (absolute paths):"
  for p in "${DECLARED_PATHS[@]}"; do
    if [ -e "$p" ]; then
      sz=$(stat -c%s "$p" 2>/dev/null || echo 0)
      if [ "$sz" -le "$MAX" ] && command -v sha256sum >/dev/null 2>&1; then
        h="$(sha256sum "$p" | awk "{print \$1}")"
        echo "- $p  (size=${sz}, sha256=${h})"
      else
        echo "- $p  (size=${sz})"
      fi
      # 同步一份 pointer 放 payload（即使沒被 INCLUDE 到）
      add_file "$p"
    else
      echo "- $p  (MISSING)"
    fi
  done
} > "$MAN"

# 產出（最多 10 個檔；超過就打成 1 個 tar.gz）
# 計算 payload 內的實體與 .pointer 檔數
mapfile -d '' LIST < <(cd "$PAY" && find . -type f -print0)
COUNT="${#LIST[@]}"
STAMP="$(date +%Y%m%dT%H%M%S)"
if [ "$COUNT" -gt 10 ]; then
  ART="$OUT_DIR/project_payload_${STAMP}.tar.gz"
  tar -C "$PAY" -czf "$ART" .
  echo "$ART"
else
  # 輸出目錄，讓你可直接逐檔上傳（<=10）
  PK="$OUT_DIR/project_payload_${STAMP}"
  mkdir -p "$PK"
  cp -a "$PAY/." "$PK/"
  # 顯示每一個檔案的絕對路徑
  (cd "$PK" && find . -type f | sed "s|^.|$PK|")
  echo "$PK"
fi
