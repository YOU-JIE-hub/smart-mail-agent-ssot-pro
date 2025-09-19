#!/usr/bin/env bash
set -Eeuo pipefail
umask 022

ROOT="${1:-/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox}"

# 自動猜三個資料夾（或你也可以用參數 3 個明確指定）
CAND=()
while IFS= read -r -d '' d; do CAND+=("$d"); done < <(find "$ROOT" -maxdepth 2 -type d -print0 2>/dev/null || true)

pick_dir() {
  local key="$1"
  for d in "${CAND[@]}"; do
    bn="$(basename "$d" | tr '[:upper:]' '[:lower:]')"
    if [[ "$bn" == *"$key"* ]]; then echo "$d"; return 0; fi
  done
  return 1
}

INTENT_DIR="${2:-$(pick_dir intent || true)}"
SPAM_DIR="${3:-$(pick_dir spam || true)}"
KIE_DIR="${4:-$(pick_dir kie || pick_dir bundle || true)}"

pretty_tree () {
  local base="$1"
  if command -v tree >/dev/null 2>&1; then
    tree -a -L 4 "$base" || true
  else
    # find 版簡易 tree
    echo ">>> $base"
    (cd "$base" && find . -maxdepth 4 | sort) || true
  fi
}

echo "[ROOT] $ROOT"
[[ -n "${INTENT_DIR:-}" ]] && { echo "[INTENT] $INTENT_DIR"; pretty_tree "$INTENT_DIR"; echo; } || echo "[INTENT] 未找到"
[[ -n "${SPAM_DIR:-}"   ]] && { echo "[SPAM]   $SPAM_DIR";   pretty_tree "$SPAM_DIR";   echo; } || echo "[SPAM] 未找到"
[[ -n "${KIE_DIR:-}"    ]] && { echo "[KIE]    $KIE_DIR";    pretty_tree "$KIE_DIR";    echo; } || echo "[KIE] 未找到"
