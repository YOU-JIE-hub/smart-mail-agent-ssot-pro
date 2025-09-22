#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/home/youjie/projects/smart-mail-agent"
# 永遠先進專案＋啟環境
if [ -f "$ROOT/.sma_tools/env_guard.sh" ]; then
  source "$ROOT/.sma_tools/env_guard.sh"
else
  cd "$ROOT" || { echo "[FATAL] project missing at $ROOT"; exit 1; }
fi

usage(){ echo "Usage: $0 [--code|--list|--here]"; exit 0; }
case "${1:-}" in -h|--help) usage;; esac
opt="${1:-}"

# 想用 VS Code
if [[ "$opt" == "--code" ]]; then
  if command -v code >/dev/null 2>&1; then (cd "$ROOT" && code .) && exit 0; fi
  echo "[WARN] 找不到 'code' 指令，改用檔案總管。"
fi

# WSL/Windows 檔案總管
if grep -qi microsoft /proc/version 2>/dev/null && command -v wslpath >/dev/null 2>&1; then
  if command -v explorer.exe >/dev/null 2>&1; then
    explorer.exe "$(wslpath -w "$ROOT")" >/dev/null 2>&1 & exit 0
  fi
fi

# macOS Finder
if [[ "$(uname -s)" == "Darwin" ]]; then
  open "$ROOT" && exit 0
fi

# Linux 檔案總管
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$ROOT" >/dev/null 2>&1 & exit 0
fi
for fm in nautilus nemo thunar dolphin pcmanfm; do
  if command -v "$fm" >/dev/null 2>&1; then "$fm" "$ROOT" >/dev/null 2>&1 & exit 0; fi
done

# 沒圖形環境 → 列表
if [[ "$opt" == "--list" || -t 1 ]]; then
  echo "[INFO] 未偵測到圖形檔案總管，列出目錄："
  if command -v tree >/dev/null 2>&1; then
    tree -a -I ".git|.venv|__pycache__|node_modules|*.pyc|.cache" -L 2 -h "$ROOT"
  else
    ls -lah "$ROOT"
  fi
fi

# 只輸出路徑
if [[ "$opt" == "--here" ]]; then
  echo "$ROOT"
fi
