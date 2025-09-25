#!/usr/bin/env bash
# 安全套用 reports_auto/_refactor/clean_plan.ndjson
# 需求：APPLY=1 才會執行；否則為 dry-run。所有改動先備份到 .sma_refactor_backups/<ts>/
set -euo pipefail
echo "SMA PRINT OK :: APPLY CLEAN PLAN"
: "${SMA_ROOT:=/home/youjie/projects/smart-mail-agent}"
: "${PLAN:=reports_auto/_refactor/clean_plan.ndjson}"
: "${APPLY:=0}"            # 1=真的執行；0=dry-run
: "${BATCH_VALIDATE:=1}"   # 1=每批後做煙霧驗證（若無測試檔不會失敗）

cd "$SMA_ROOT" || { echo "ERROR: 無法 cd $SMA_ROOT"; exit 2; }
[ -f "$PLAN" ] || { echo "ERROR: 找不到計畫檔 $PLAN"; exit 3; }

TS="$(date +%Y%m%dT%H%M%S)"
BK=".sma_refactor_backups/$TS"
MERGE_WS="reports_auto/_refactor/merges_$TS"
mkdir -p "$BK" "$MERGE_WS"

act_count=0; del_count=0; pref_count=0
dry_note="(dry-run)"
[ "$APPLY" = "1" ] && dry_note=""

apply_delete() {
  local p="$1"
  [ -f "$p" ] || { echo "SKIP (不存在) DELETE $p"; return; }
  mkdir -p "$BK/$(dirname "$p")"; cp -p "$p" "$BK/$p"
  if [ "$APPLY" = "1" ]; then rm -f "$p"; fi
  echo "DELETE $p $dry_note"
  del_count=$((del_count+1))
}

apply_prefer() {
  local win="$1"; local lose="$2"
  if [ -f "$lose" ]; then
    mkdir -p "$BK/$(dirname "$lose")"; cp -p "$lose" "$BK/$lose"
    mkdir -p "$MERGE_WS/$(dirname "$lose")"; cp -p "$lose" "$MERGE_WS/$lose"
    if [ "$APPLY" = "1" ]; then rm -f "$lose"; fi
    echo "PREFER keep=$win  drop=$lose $dry_note"
    pref_count=$((pref_count+1))
  else
    echo "SKIP (不存在) PREFER drop=$lose"
  fi
}

# 逐行處理 ndjson
while IFS= read -r line || [ -n "$line" ]; do
  [ -z "$line" ] && continue
  action="$(echo "$line" | jq -r '.action')"
  case "$action" in
    ENTRY_KEEP)
      echo "KEEP $(echo "$line" | jq -r '.path')"
      ;;
    ENTRY_REMOVE|DELETE_DUP)
      p="$(echo "$line" | jq -r '.path')"
      apply_delete "$p"
      ;;
    PREFER)
      w="$(echo "$line" | jq -r '.winner')"
      l="$(echo "$line" | jq -r '.loser')"
      apply_prefer "$w" "$l"
      ;;
    *)
      echo "WARN: 未知 action: $line"
      ;;
  esac
  act_count=$((act_count+1))
done < "$PLAN"

echo "SUMMARY: actions=$act_count delete=$del_count prefer=$pref_count (backups at $BK; merges at $MERGE_WS)"

# 煙霧驗證（可選）
if [ "$BATCH_VALIDATE" = "1" ]; then
  echo "SMA PRINT OK :: VALIDATE (pytest & minimal smoke)"
  if command -v pytest >/dev/null; then
    pytest -q || echo "WARN: pytest 非 0（請檢查失敗用例）"
  fi
  # 最小煙霧：只檢查關鍵目錄存在
  test -d src/smart_mail_agent || echo "WARN: src/smart_mail_agent 不存在"
  test -d src/ai_rpa || echo "WARN: src/ai_rpa 不存在"
fi

echo "SMA PRINT OK :: APPLY DONE"
