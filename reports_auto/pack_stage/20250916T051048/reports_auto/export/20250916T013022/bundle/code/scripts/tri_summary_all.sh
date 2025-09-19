#!/usr/bin/env bash
# tri_summary_all.sh — 三段式評測匯總（單一 .err + LATEST + 健康檢查 + 企業級摘要）
set -Eeuo pipefail -o errtrace
ROOT="${ROOT:-/home/youjie/projects/smart-mail-agent-ssot-pro}"; cd "$ROOT"
TS="$(date +%Y%m%dT%H%M%S)"
RUN_DIR="reports_auto/tri_summary/${TS}"
LOG="$RUN_DIR/run.log"; ERR="$RUN_DIR/tri_summary.err"; PY_LAST="$RUN_DIR/py_last_trace.txt"
STATUS_DIR="reports_auto/status"
mkdir -p "$RUN_DIR" "$STATUS_DIR" reports_auto/.quarantine
: > "$ERR"

print_paths(){ echo "[PATHS]"; for k in RUN_DIR LOG ERR PY_LAST; do v="$(eval echo \$$k)"; echo "  $(printf '%-7s' $k)= $(cd "$(dirname "$v")" && pwd)/$(basename "$v")"; done; }
on_err(){ c=${1:-$?}; { echo "=== BASH_TRAP ==="; echo "TIME: $(date -Is)"; echo "LAST: ${BASH_COMMAND:-<none>}"; echo "CODE: $c"; } >>"$RUN_DIR/last_trace.txt"; echo "exit_code=$c" > "$ERR"; print_paths; echo "[FATAL] tri-summary failed (code=$c) — see files above"; exit "$c"; }
on_exit(){ ln -sfn "$RUN_DIR" reports_auto/LATEST || true; print_paths; echo "[*] REPORT DIR ready"; command -v explorer.exe >/dev/null 2>&1 && explorer.exe "$(wslpath -w "$(cd "$RUN_DIR"&&pwd)")" >/dev/null 2>&1 || true; }
trap 'on_err $?' ERR; trap on_exit EXIT
{ exec > >(tee -a "$LOG") 2>&1; } || { exec >>"$LOG" 2>&1; }
PS4='+ tri-sum:${LINENO}: '; set -x

# 0) 鎖定最近一次三段 run 目錄
last_of(){ ls -1dt "$1"/* 2>/dev/null | head -n1 || true; }
INT_DIR="$(last_of reports_auto/eval)"
KIE_DIR="$(last_of reports_auto/eval_kie)"
PA_DIR="$(last_of reports_auto/eval_planact)"
echo "[*] INT_DIR=${INT_DIR:-<none>}"
echo "[*] KIE_DIR=${KIE_DIR:-<none>}"
echo "[*] PA_DIR=${PA_DIR:-<none>}"

# 1) 讀取 JSON 結果（存在才讀）
to_abs(){ [ -n "$1" ] && cd "$1" 2>/dev/null && pwd; }
INT_JSON="${INT_DIR:+$INT_DIR/tri_results.json}"
KIE_JSON="${KIE_DIR:+$KIE_DIR/tri_results_kie.json}"
PA_JSON="${PA_DIR:+$PA_DIR/tri_results_planact.json}"

# 2) 生成摘要（Python 完成聚合與一致性檢查）
python - "$INT_JSON" "$KIE_JSON" "$PA_JSON" "$RUN_DIR" "$PY_LAST" <<'PY'
import os, sys, json, pathlib, traceback, faulthandler
INT, KIE, PA, RUN_DIR, PY_LAST = [pathlib.Path(p) if i<3 and p else None for i,p in enumerate(sys.argv[1:4])] + [pathlib.Path(sys.argv[4]), pathlib.Path(sys.argv[5])]
faulthandler.enable(open(RUN_DIR/"py_run.log","w",encoding="utf-8"))
def jload(p): 
    if not p or not p.exists(): return None
    with open(p,"r",encoding="utf-8") as f: return json.load(f)

try:
    out = {
      "intents": jload(INT),
      "kie": jload(KIE),
      "planact": jload(PA),
      "ts": os.path.basename(str(RUN_DIR))
    }
    # names==seeds==sent 檢查（都有時才比）
    names = out["intents"]["n"] if out["intents"] else None
    seeds = out["kie"]["n"] if out["kie"] else None
    sent  = out["planact"]["n"] if out["planact"] else None
    out["health"] = {"names":names,"seeds":seeds,"sent":sent,"equal": (names==seeds==sent) if None not in (names,seeds,sent) else None}
    (RUN_DIR/"tri_summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
except Exception:
    PY_LAST.write_text(traceback.format_exc(),encoding="utf-8")
    raise
PY

# 3) 產企業級 Markdown 報告
RUN_NAME="$(basename "$RUN_DIR")"; MD="$STATUS_DIR/TRI_SUMMARY_${RUN_NAME}.md"
{
  echo "# TRI-SUMMARY ${RUN_NAME}"
  echo "## 分類（INTENTS）"
  if [ -f "$INT_DIR/tri_results.json" ]; then
    echo "- RUN: $(cd "$INT_DIR" && pwd)"
    echo "- RESULTS: $(cd "$INT_DIR" && pwd)/tri_results.json"
    echo "- LOG: $(cd "$INT_DIR" && pwd)/run.log"
    echo "- ERR: $(cd "$INT_DIR" && pwd)/tri_eval.err"
    echo "- PY_LAST: $(cd "$INT_DIR" && pwd)/py_last_trace.txt"
  else
    echo "- 未找到 tri_results.json"
  fi
  echo "## 抽取（KIE）"
  if [ -f "$KIE_DIR/tri_results_kie.json" ]; then
    echo "- RUN: $(cd "$KIE_DIR" && pwd)"
    echo "- RESULTS: $(cd "$KIE_DIR" && pwd)/tri_results_kie.json"
    echo "- LOG: $(cd "$KIE_DIR" && pwd)/run.log"
    echo "- ERR: $(cd "$KIE_DIR" && pwd)/kie_eval.err"
    echo "- PY_LAST: $(cd "$KIE_DIR" && pwd)/py_last_trace.txt"
  else
    echo "- 未找到 tri_results_kie.json"
  fi
  echo "## 規劃+動作（PLAN/ACT）"
  if [ -f "$PA_DIR/tri_results_planact.json" ]; then
    echo "- RUN: $(cd "$PA_DIR" && pwd)"
    echo "- RESULTS: $(cd "$PA_DIR" && pwd)/tri_results_planact.json"
    echo "- LOG: $(cd "$PA_DIR" && pwd)/run.log"
    echo "- ERR: $(cd "$PA_DIR" && pwd)/planact.err"
    echo "- PY_LAST: $(cd "$PA_DIR" && pwd)/py_last_trace.txt"
  else
    echo "- 未找到 tri_results_planact.json"
  fi
  echo "## 健康檢查"
  echo "- tri_summary.json: $(cd "$RUN_DIR" && pwd)/tri_summary.json"
} > "$MD"

echo "[OK] TRI summary generated -> $MD"
