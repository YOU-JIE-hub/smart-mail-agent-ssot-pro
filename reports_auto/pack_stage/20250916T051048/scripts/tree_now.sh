#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/scan/${TS}"; mkdir -p "$OUT"
ERR_DIR="$ROOT/reports_auto/ERR"; mkdir -p "$ERR_DIR"

RUNLOG="$OUT/run.log"
ERRFILE="$OUT/scan.err"
WHERE="$ERR_DIR/where.txt"
TREE_TXT="$OUT/tree.txt"
MANIFEST="$OUT/manifest.jsonl"
HUGE_TXT="$OUT/huge_files.txt"
TOPN_TXT="$OUT/top50_by_size.txt"
STATS="$OUT/stats.json"

# 門檻（可被環境變數覆蓋）
MAX=$((256*1024*1024))                   # 大檔定義 (256MB)
HASH_MAX_BYTES=${HASH_MAX_BYTES:-$((64*1024*1024))}  # 每檔最多雜湊 64MB
HASH_MAX_FILES=${HASH_MAX_FILES:-4000}               # 最多雜湊 4000 檔
PROGRESS_EVERY=${PROGRESS_EVERY:-500}               # 每 500 檔列一次進度

print_paths(){ cat <<EOF
[PATHS]
  OUT_DIR=$(cd "$OUT" && pwd)
  TREE=$(cd "$OUT" && pwd)/tree.txt
  MANIFEST=$(cd "$OUT" && pwd)/manifest.jsonl
  HUGE=$(cd "$OUT" && pwd)/huge_files.txt
  TOPN=$(cd "$OUT" && pwd)/top50_by_size.txt
  STATS=$(cd "$OUT" && pwd)/stats.json
EOF
}

mirror_err(){
  cp -f "$RUNLOG" "$ERR_DIR/run.log" 2>/dev/null || true
  cp -f "$ERRFILE" "$ERR_DIR/scan.err" 2>/dev/null || true
  printf "RUN_DIR=%s\n" "$(cd "$OUT" && pwd)" > "$WHERE"
}

on_err(){ ec=${1:-$?}
  {
    echo "=== BASH_TRAP(tree_now) ==="
    echo "TIME: $(date -Is)"
    echo "LAST: ${BASH_COMMAND:-<none>}"
    echo "CODE: $ec"
  } >> "$OUT/last_trace.txt"
  echo "exit_code=$ec" > "$ERRFILE"
  mirror_err
  print_paths
  exit "$ec"
}
on_exit(){
  : > "$ERRFILE"   # 成功也產生空 err 檔，方便你固定讀
  mirror_err
  print_paths
}
trap 'on_err $?' ERR
trap on_exit EXIT

# ========== 工具 ==========
bytes_human(){ # $1: bytes -> 例如 1.23G
  local b=$1 u=(B KB MB GB TB) i=0
  while (( b>=1024 && i<${#u[@]}-1 )); do b=$((b/1024)); ((i++)); done
  echo "${b}${u[$i]}"
}

hash_file(){ # $1: file path（限制大小與數量）
  local f="$1"
  if (( HASHED_COUNT >= HASH_MAX_FILES )); then echo ""; return 0; fi
  local sz; sz=$(stat -c %s "$f" 2>/dev/null || echo 0)
  local lim=$sz; (( lim>HASH_MAX_BYTES )) && lim=$HASH_MAX_BYTES
  # 若檔案為 0 直接給空字串；否則部分雜湊
  if (( lim>0 )); then
    head -c "$lim" -- "$f" | sha256sum 2>/dev/null | awk '{print $1}'
    ((HASHED_COUNT++))
  else
    echo ""
  fi
}

emit_jsonl(){ # 用 jq -n 保證是合法 JSON
  local path="$1" type="$2" size="$3" mtime_iso="$4" sha="$5"
  jq -n --arg path "$path" --arg type "$type" --arg mtime "$mtime_iso" \
        --arg sha "$sha" --argjson size "${size:-0}" \
        '{path:$path,type:$type,size_bytes:$size,mtime:$mtime} + ( $sha|length>0 ? {sha256:$sha} : {} )'
}

# ========== 掃描 ==========
{
  echo "[*] tree_now start @ $TS"
  echo "[*] HASH_MAX_BYTES=$HASH_MAX_BYTES HASH_MAX_FILES=$HASH_MAX_FILES PROGRESS_EVERY=$PROGRESS_EVERY"
  echo "[*] PWD=$(pwd)"
  echo "[*] uname=$(uname -a)"
  echo "[*] df -h | head"; df -h | head
  echo
  echo "[*] build tree.txt"
} >> "$RUNLOG" 2>&1

# 樹狀（不用 tree 指令）：顯示相對路徑
( cd "$ROOT" && find . -mindepth 1 -printf '%P\n' | sort ) \
  | awk -F/ '{
      indent=""; for(i=1;i<NF;i++) indent=indent "  ";
      print indent $NF
    }' > "$TREE_TXT"

echo "[*] build manifest.jsonl" >> "$RUNLOG"

# 逐檔輸出 JSONL（null 分隔）
HASHED_COUNT=0
COUNT=0
: > "$MANIFEST"
while IFS= read -r -d '' p; do
  ((COUNT++))
  if (( COUNT % PROGRESS_EVERY == 0 )); then
    echo "[..] scanned $COUNT" >> "$RUNLOG"
  fi
  abs="$(cd "$(dirname "$p")" && pwd)/$(basename "$p")"
  if [ -h "$p" ]; then
    type="symlink"
    size=0
    mtiso="$(date -Is -r "$(stat -c %Y "$p" 2>/dev/null || echo 0)" 2>/dev/null || echo "")"
    sha=""
  elif [ -d "$p" ]; then
    type="dir"
    size=0
    mtiso="$(date -Is -r "$(stat -c %Y "$p" 2>/dev/null || echo 0)" 2>/dev/null || echo "")"
    sha=""
  else
    type="file"
    size="$(stat -c %s "$p" 2>/dev/null || echo 0)"
    mtiso="$(date -Is -r "$(stat -c %Y "$p" 2>/dev/null || echo 0)" 2>/dev/null || echo "")"
    sha="$(hash_file "$p")"
  fi
  emit_jsonl "$abs" "$type" "$size" "$mtiso" "$sha" >> "$MANIFEST"
done < <(find . -mindepth 1 -print0)

# 大檔清單
jq -r --argjson max "$MAX" 'select(.type=="file" and .size_bytes > $max) | "\(.size_bytes)\t\(.path)"' "$MANIFEST" \
  | sort -nr | awk -F'\t' '{printf "%12d  %s\n",$1,$2}' > "$HUGE_TXT" || true

# TopN by size
jq -r 'select(.type=="file") | "\(.size_bytes)\t\(.path)"' "$MANIFEST" \
  | sort -nr | head -50 | awk -F'\t' '{printf "%12d  %s\n",$1,$2}' > "$TOPN_TXT" || true

# 統計
jq -n --slurpfile m "$MANIFEST" '
  def sum(s): reduce s as $x (0; . + $x);
  def count(s): reduce s as $x (0; . + 1);
  ($m[0] // []) as $a
  | {
      scanned: ($a|length),
      files:   ($a|map(select(.type=="file"))|length),
      dirs:    ($a|map(select(.type=="dir"))|length),
      symlinks:($a|map(select(.type=="symlink"))|length),
      total_size: ($a|map(select(.type=="file")|.size_bytes)|add // 0),
      large_over_256mb: ($a|map(select(.type=="file" and .size_bytes> (256*1024*1024)))|length),
      hashed_files: ($a|map(select(.sha256!=null))|length)
    }' > "$STATS"

# 完成訊息
{
  echo
  echo "[OUT]   $OUT"
  echo "[TREE]  $TREE_TXT"
  echo "[MANI]  $MANIFEST"
  echo "[HUGE]  $HUGE_TXT"
  echo "[TOPN]  $TOPN_TXT"
  echo "[STATS] $STATS"
} | tee -a "$RUNLOG"

# 固定錯誤出口與 where
: > "$ERRFILE"
printf "RUN_DIR=%s\n" "$(cd "$OUT" && pwd)" > "$WHERE"
cp -f "$RUNLOG" "$ERR_DIR/run.log" 2>/dev/null || true
cp -f "$ERRFILE" "$ERR_DIR/scan.err" 2>/dev/null || true
