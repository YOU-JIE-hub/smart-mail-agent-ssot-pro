#!/usr/bin/env bash
# 列出 reports_auto/{spam,intent,kie} 或根目錄下 {spam,intent,kie} 的樹狀；若沒有資料夾就列 ZIP 內容
set -Ee -o pipefail

ROOT="${1:-/home/youjie/projects/smart-mail-agent}"
cd "$ROOT" || { echo "[FATAL] no project at $ROOT"; exit 1; }
[ -f .venv/bin/activate ] && . .venv/bin/activate
export PYTHONNOUSERSITE=1
export PYTHONPATH=".:scripts:.sma_tools:${PYTHONPATH:-}"

mkdir -p reports_auto/_inspect
OUT="reports_auto/_inspect/three_bundles_tree.txt"

list_tree() {
  local path="$1"
  if command -v tree >/dev/null 2>&1; then
    tree -a -I ".git|.venv|__pycache__|node_modules|*.pyc|.cache" -L 6 -h "$path" 2>/dev/null || true
  else
    find "$path" -maxdepth 6 -printf "%y %6s %TY-%Tm-%Td %TH:%TM %p\n" 2>/dev/null | sed 's/^/  /'
  fi
}

dirs=(reports_auto/spam reports_auto/intent reports_auto/kie spam intent kie)
found=0

{
  echo "# Three Bundles Tree"
  echo "- Project root: $ROOT"
  echo "- Generated: $(date '+%F %T')"
  echo
  for d in "${dirs[@]}"; do
    if [[ -d "$d" ]]; then
      found=1
      echo "===== $d ====="
      list_tree "$d"
      echo
    fi
  done
  if [[ $found -eq 0 ]]; then
    echo "[WARN] 找不到已解壓的資料夾；改列 ZIP 內容："
    for z in reports_auto/spam.zip reports_auto/intent.zip reports_auto/kie.zip; do
      if [[ -f "$z" ]]; then
        echo "=== ZIP: $z ==="
        if command -v unzip >/dev/null 2>&1; then unzip -l "$z"; else bsdtar -tf "$z"; fi
        echo
      else
        echo "缺：$z"
      fi
    done
  fi
} | tee "$OUT"

echo "[OK] 輸出 -> $OUT"
