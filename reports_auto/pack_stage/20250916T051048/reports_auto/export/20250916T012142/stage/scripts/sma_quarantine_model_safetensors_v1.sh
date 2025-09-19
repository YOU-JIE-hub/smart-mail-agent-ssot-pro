#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$(pwd)}"
TS="$(date +%Y%m%d_%H%M%S)"
Q="$ROOT/reports_auto/quarantine_models_$TS"
LOG="$Q/quarantine_log.csv"
mkdir -p "$Q"; echo 'action,fullpath,bytes,keeper,ts' > "$LOG"

# 收集候選（包含 model.safetensors 與其尾綴檔，如 .bak、.tmp 等）
mapfile -d '' -t CAND < <(find "$ROOT" -type f \( -name 'model.safetensors' -o -name 'model.safetensors.*' \) -print0 2>/dev/null)

if (( ${#CAND[@]} == 0 )); then
  echo "[INFO] 找不到任何 model.safetensors* 檔案"; exit 0
fi

# 決定要保留的檔
KEEP="${KEEP:-}"
if [[ -n "$KEEP" && -f "$KEEP" ]]; then
  K="$KEEP"
elif [[ -f "$ROOT/artifacts_kie/model/model.safetensors" ]]; then
  K="$ROOT/artifacts_kie/model/model.safetensors"
else
  K="${CAND[0]}"
fi
echo "[KEEP] $K"

# 搬移其餘檔案到隔離夾（保留相對路徑）
BYTES=0
for f in "${CAND[@]}"; do
  if [[ "$f" == "$K" ]]; then
    echo "keep,$f,0,$K,$(date -Iseconds)" >> "$LOG"
    continue
  fi
  sz=$(stat -c %s -- "$f" 2>/dev/null || echo 0)
  rel="${f#$ROOT/}"
  dest="$Q/$rel"
  mkdir -p "$(dirname "$dest")"
  mv -f -- "$f" "$dest"
  echo "move,$f,$sz,$K,$(date -Iseconds)" >> "$LOG"
  BYTES=$((BYTES + sz))
done

echo "== 完成 =="
echo "搬移總量: $((BYTES/1024/1024)) MiB"
echo "隔離夾: $Q"
# 自動用 Windows 檔案總管打開隔離夾（WSL）
/mnt/c/Windows/explorer.exe "$(wslpath -w "$Q")" >/dev/null 2>&1 || true
