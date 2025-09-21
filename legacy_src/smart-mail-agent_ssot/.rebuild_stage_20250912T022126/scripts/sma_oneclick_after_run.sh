#!/usr/bin/env bash
# 一鍵後處理：挑最新 E2E → 如無則建立 → 如空則回填 → 文本回填 → 重路由 → 產物 → 驗證 → 報告
set -Eeuo pipefail
set -o pipefail

TS="$(date +%Y%m%dT%H%M%S)"
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
ERRDIR="$ROOT/reports_auto/errors/ONECLICK_AFTER_${TS}"
STATUS_DIR="$ROOT/reports_auto/status"
LOG="$ERRDIR/run.log"
mkdir -p "$ERRDIR" "$STATUS_DIR" "$ROOT/reports_auto/e2e_mail"

log()   { printf '%s\n' "$*" | tee -a "$LOG" >&2; }
warn()  { printf '[WARN] %s\n' "$*" | tee -a "$LOG" >&2; }
fatal() { printf '[FATAL] %s\n' "$*" | tee -a "$LOG" >&2; exit 2; }
trap 'echo "[ERR] line=$LINENO" | tee -a "$LOG" >&2' ERR

cd "$ROOT"
export PYTHONNOUSERSITE=1
export PYTHONPATH=".:src:scripts:.sma_tools:${PYTHONPATH:-}"
[ -f ".venv/bin/activate" ] && . .venv/bin/activate || true

RUN_DIR_OVERRIDE="${1:-}"  # 可傳入 --run-dir <path>
if [ "$RUN_DIR_OVERRIDE" = "--run-dir" ]; then shift; RUN_DIR_OVERRIDE="${1:-}"; shift || true; fi

pick_run_dir() {
  local base="$ROOT/reports_auto/e2e_mail"
  [ -d "$base" ] || { echo ""; return; }
  # 只輸出路徑，不輸出任何其它字串
  mapfile -t dirs < <(find "$base" -maxdepth 1 -type d -regex '.*/[0-9]{8}T[0-9]{6}$' -printf "%T@ %p\n" | sort -nr | awk '{print $2}')
  for d in "${dirs[@]}"; do
    [ -f "$d/cases.jsonl" ] && { printf '%s\n' "$d"; return; }
  done
  echo ""
}

is_ts_dir() {
  # 驗證是否為 reports_auto/e2e_mail/<timestamp> 型式
  [[ "$1" =~ /reports_auto/e2e_mail/[0-9]{8}T[0-9]{6}$ ]]
}

ensure_run_dir() {
  local rd=""
  if [ -n "${RUN_DIR_OVERRIDE:-}" ]; then
    rd="$RUN_DIR_OVERRIDE"
    [ -d "$rd" ] || fatal "指定的 run 目錄不存在：$rd"
    printf '%s\n' "$rd"
    return
  fi

  rd="$(pick_run_dir || true)"
  if [ -z "$rd" ]; then
    log "[INFO] 找不到可用 run，嘗試建立一個"
    # 將一鍵 E2E 的輸出全數重導到 LOG，避免污染 stdout
    bash sma_oneclick_all.sh >>"$LOG" 2>&1 || warn "sma_oneclick_all.sh 失敗，將回退到舊樣本"
    rd="$(pick_run_dir || true)"
  fi

  if [ -z "$rd" ] && [ -d "$ROOT/reports_auto/e2e_mail/20250902T144500" ]; then
    rd="$ROOT/reports_auto/e2e_mail/20250902T144500"
    log "[INFO] 回退到舊樣本：$rd"
  fi

  [ -n "$rd" ] || fatal "找不到可用的 E2E 目錄（需含 cases.jsonl 或可被回填）"
  # 正規化與驗證
  rd="$(readlink -f "$rd" || printf '%s' "$rd")"
  is_ts_dir "$rd" || warn "run_dir 非標準時間戳目錄：$rd"
  printf '%s\n' "$rd"
}

RUN_DIR="$(ensure_run_dir)"
log "[INFO] run_dir=$RUN_DIR"

# cases.jsonl 若不存在或為空：先 DB 回填，仍空則造 10 筆合成樣本
need_patch=0
if [ ! -f "$RUN_DIR/cases.jsonl" ]; then
  need_patch=1
else
  nb=$(grep -cve '^[[:space:]]*$' "$RUN_DIR/cases.jsonl" || true)
  [ "${nb:-0}" -eq 0 ] && need_patch=1
fi

if [ "$need_patch" = "1" ]; then
  log "[INFO] cases.jsonl 缺失或為空，先嘗試 DB 回填"
  python scripts/sma_patch_cases_from_db.py --run-dir "$RUN_DIR" >>"$LOG" 2>&1 || true
  nb=$(grep -cve '^[[:space:]]*$' "$RUN_DIR/cases.jsonl" || true)
  if [ "${nb:-0}" -eq 0 ]; then
    warn "DB 回填後仍為空，寫入合成佔位 10 筆"
    python - "$RUN_DIR" >>"$LOG" 2>&1 <<'PY'
import json, sys, time
from pathlib import Path
run = Path(sys.argv[1])
p = run/"cases.jsonl"
ts=time.strftime("%Y%m%dT%H%M%S")
ints=["報價","技術支援","投訴","規則詢問","資料異動","其他"]
rows=[{"id":f"synthetic_{ts}_{i:03d}",
       "case_id":f"synthetic_{ts}_{i:03d}",
       "intent":ints[i%len(ints)],
       "fields":{"spans":[{"label":"amount","value":"NT$ 10,000","start":0,"end":0}]},
       "text":f"意圖:{ints[i%len(ints)]}；欄位:amount=NT$10,000；關鍵詞:報價 試算 折扣 採購 合約 SOW"} for i in range(10)]
p.write_text("\n".join(json.dumps(r,ensure_ascii=False) for r in rows)+"\n", encoding="utf-8")
print("[OK] wrote synthetic cases:", p)
PY
  fi
fi

# 文本回填 → 重路由 → 產物 → 驗證（各步驟錯誤不阻斷，全部寫 LOG）
python scripts/sma_e2e_enrich_cases_text.py --run-dir "$RUN_DIR" >>"$LOG" 2>&1 || true
python scripts/sma_reroute_last_run_intent.py --run-dir "$RUN_DIR" >>"$LOG" 2>&1 || true
python scripts/sma_make_rpa_placeholders.py --run-dir "$RUN_DIR" >>"$LOG" 2>&1 || true
python scripts/validate_rpa_outputs.py >>"$LOG" 2>&1 || true

# 摘要
Q=$(find "$RUN_DIR/rpa_out/quotes" -type f -name '*.html' 2>/dev/null | wc -l | tr -d ' ')
T=$(find "$RUN_DIR/rpa_out/tickets" -type f -name '*.json' 2>/dev/null | wc -l | tr -d ' ')
F=$(find "$RUN_DIR/rpa_out/faq_replies" -type f -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
D=$(find "$RUN_DIR/rpa_out/diffs" -type f -name '*.json' 2>/dev/null | wc -l | tr -d ' ')
E=$(find "$RUN_DIR/rpa_out/email_outbox" -type f -name '*.eml' 2>/dev/null | wc -l | tr -d ' ')
S_MD="$STATUS_DIR/ONECLICK_AFTER_${TS}.md"

{
  echo "# One-click After-run Summary ($TS)"
  echo "- run_dir: ${RUN_DIR#"$ROOT/"}"
  echo "- intent_thresholds: $(realpath --relative-to="$ROOT" reports_auto/intent_thresholds.json 2>/dev/null || echo '-')"
  [ -f "$RUN_DIR/TEXT_ENRICH_SUMMARY.md" ] && echo "- text_enrich: present" || echo "- text_enrich: -"
  [ -f "$RUN_DIR/intent_reroute_summary.md" ] && echo "- reroute: present" || echo "- reroute: -"
  [ -f "$RUN_DIR/PATCH_CASES_SUMMARY.md" ] && echo "- patch_cases: present" || echo "- patch_cases: -"
  echo "## RPA outputs"
  echo "- quotes: $Q"
  echo "- tickets: $T"
  echo "- faq_replies: $F"
  echo "- diffs: $D"
  echo "- email_outbox: $E"
  echo "## Files"
  for f in PATCH_CASES_SUMMARY.md TEXT_ENRICH_SUMMARY.md intent_reroute_summary.md intent_reroute_audit.csv intent_reroute_suggestion.ndjson; do
    [ -f "$RUN_DIR/$f" ] && echo "- ${RUN_DIR#"$ROOT/"}/$f"
  done
} > "$S_MD"

cp -f "$S_MD" "$STATUS_DIR/LATEST.md"
echo "[RESULT] summary -> $S_MD"
echo "[RESULT] latest  -> $STATUS_DIR/LATEST.md"
echo "[LOG]     detail  -> $LOG"
