#!/usr/bin/env bash
set -Eeuo pipefail

PROJ="${PROJ:-$HOME/projects/smart-mail-agent_ssot}"
EMLDIR="${EMLDIR:-data/demo_eml}"
TIMEOUT_IMPORT="${TIMEOUT_IMPORT:-20}"
TIMEOUT_E2E="${TIMEOUT_E2E:-120}"
HEARTBEAT_INT="${HEARTBEAT_INT:-0.5}"

cd "$PROJ"
mkdir -p diag

# -- venv & 基本環境 --
python3 -m venv .venv 2>/dev/null || true
. .venv/bin/activate
export PYTHONUNBUFFERED=1 PYTHONFAULTHANDLER=1
export PYTHONPATH="$PROJ/src:${PYTHONPATH:-}"
# 限制 BLAS 執行緒避免載入時狂吃 CPU
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1

# 清理 .pth，只留 src；移除任何 import usercustomize
SP="$(python - <<'PY'
import sysconfig
print(sysconfig.get_paths().get("purelib") or sysconfig.get_paths().get("platlib"))
PY
)"
printf '%s\n' "$PROJ/src" > "$SP/zzz_sma_root.pth"
shopt -s nullglob
for p in "$SP"/*.pth; do sed -i '/import[[:space:]]\+usercustomize/d' "$p" || true; done

echo "[diag] artifacts & sizes"
ls -lh artifacts_prod 2>/dev/null || true
for f in artifacts_prod/model_pipeline.pkl artifacts_prod/ens_thresholds.json artifacts_prod/intent_rules_calib_v11c.json; do
  [ -f "$f" ] && echo "  - $f $(stat -c %s "$f" 2>/dev/null) bytes" || echo "  - MISSING: $f"
done

# ---- 輕量 schema 校正，避免 DB 卡鎖/缺欄位 ----
python - <<'PY'
import sqlite3, os
os.makedirs("db", exist_ok=True)
conn = sqlite3.connect("db/sma.sqlite"); cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS actions (id TEXT PRIMARY KEY, case_id TEXT, action_type TEXT, path TEXT, created_at TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS intent_preds (case_id TEXT)")
def ensure(t,c,ddl):
    cols=[r[1] for r in cur.execute(f"PRAGMA table_info({t})")]
    if c not in cols: cur.execute(f"ALTER TABLE {t} ADD COLUMN {c} {ddl}")
for t,c,ddl in [
    ("intent_preds","label","TEXT"),("intent_preds","confidence","REAL"),("intent_preds","created_at","TEXT"),
    ("kie_spans","case_id","TEXT"),("kie_spans","key","TEXT"),("kie_spans","value","TEXT"),("kie_spans","start","INT"),("kie_spans","end","INT"),
    ("err_log","ts","TEXT"),("err_log","case_id","TEXT"),("err_log","err","TEXT"),
]:
    try: ensure(t,c,ddl)
    except Exception: pass
conn.commit(); conn.close()
PY

echo "[diag] IMPORT (安全模式 + 逾時 ${TIMEOUT_IMPORT}s)"
# 1) 先用 importlib.find_spec 驗證 module 存在（不執行 top-level）
python - <<'PY'
import importlib.util, sys
spec = importlib.util.find_spec("smart_mail_agent.cli.e2e")
print("[import] spec:", bool(spec))
print("[import] file:", getattr(spec, "origin", None))
PY

# 2) 有逾時保護的「帶追蹤」import：若卡住，自動把全執行緒堆疊與 import trace 寫檔
timeout "$TIMEOUT_IMPORT" python - <<'PY' 2>diag/import_hang_stderr.log || echo "[import] timeout (tracebacks captured)"
import sys, os, time, importlib, faulthandler, signal
from datetime import datetime
trace_f = open("diag/import_hang_tb.txt", "w", encoding="utf-8")
faulthandler.enable(file=trace_f, all_threads=True)
# 每 5 秒 dump 一次堆疊，直到程式結束（若沒卡住，檔案就短短一點）
faulthandler.dump_traceback_later(5, repeat=True, file=trace_f)

# 追蹤 import 流（記錄 find_spec）
log = open("diag/import_trace.log", "w", encoding="utf-8")
import importlib.machinery, importlib._bootstrap_external as _be
orig_find_spec = importlib.machinery.PathFinder.find_spec
def wrapped_find_spec(fullname, path=None, target=None):
    t = datetime.utcnow().isoformat()+"Z"
    try:
        spec = orig_find_spec(fullname, path, target)
        where = getattr(spec, "origin", None) if spec else None
        log.write(f"{t}\t{fullname}\t{where}\n"); log.flush()
        return spec
    except Exception as e:
        log.write(f"{t}\t{fullname}\tERROR:{e}\n"); log.flush()
        raise
importlib.machinery.PathFinder.find_spec = wrapped_find_spec

t0=time.perf_counter()
import smart_mail_agent.cli.e2e as ee
dt=time.perf_counter()-t0
print(f"[import] smart_mail_agent.cli.e2e OK in {dt:.3f}s")
PY

# 3) 也做一次 importtime（加逾時），把結果存檔不阻塞流程
timeout "$TIMEOUT_IMPORT" python -X importtime -c 'import smart_mail_agent.cli.e2e' \
  2> diag/import_time.log || echo "[importtime] timeout (see import_trace.log/import_hang_tb.txt)"

echo "[diag] 尾端 import_time.log"
tail -n 40 diag/import_time.log 2>/dev/null || echo "(no import_time.log)"

echo "[diag] 可能的 top-level 重活掃描（joblib/load/requests/smtplib/openai/torch）"
grep -RInE 'joblib\.load|requests\.|smtplib|imaplib|openai|torch|from\s+transformers|os\.environ\[[^]]+\]|subprocess\.|time\.sleep' \
  src/smart_mail_agent | sed -n '1,120p' || true

echo "[diag] 關鍵檔案（完整列出，方便你檢視 top-level 是否在做事）"
echo "---- src/smart_mail_agent/cli/e2e.py ----"
sed -n '1,200p' src/smart_mail_agent/cli/e2e.py 2>/dev/null || echo "(missing)"
echo "---- src/smart_mail_agent/pipeline/run_action_handler.py ----"
sed -n '1,200p' src/smart_mail_agent/pipeline/run_action_handler.py 2>/dev/null || echo "(missing)"
echo "---- scripts/sma_e2e_mail.py (fallback) ----"
sed -n '1,160p' scripts/sma_e2e_mail.py 2>/dev/null || echo "(missing)"

# ---- 正式跑 E2E（有逾時 + 心跳）----
echo "[diag] run E2E (timeout ${TIMEOUT_E2E}s)"
( timeout "$TIMEOUT_E2E" python -u -m smart_mail_agent.cli.e2e "$EMLDIR" ) & pid=$!
start=$(date +%s)
while kill -0 "$pid" 2>/dev/null; do
  printf "\r[hb] running E2E... %3ds " $(( $(date +%s) - start ))
  sleep "$HEARTBEAT_INT"
done
echo
wait "$pid" || true
RC=$?
echo "[diag] E2E rc=$RC"

# ---- NDJSON gap 分析（最大卡點在哪）----
echo "[diag] NDJSON gap analysis"
python - <<'PY'
import os, json, datetime as dt
p="reports_auto/logs/pipeline.ndjson"
if not os.path.exists(p):
    print("(no pipeline.ndjson)"); raise SystemExit
rows=[]
with open(p, "r", encoding="utf-8") as f:
    for line in f:
        try:
            j=json.loads(line); ts=j.get("ts") or j.get("timestamp")
            k=j.get("kind") or j.get("event") or j.get("phase")
            if ts: rows.append((ts,k,j))
        except Exception: pass
def to_dt(s):
    try: return dt.datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(dt.timezone.utc)
    except Exception: return None
rows=[(to_dt(ts),k,j) for ts,k,j in rows if to_dt(ts)]
rows.sort(key=lambda x:x[0])
gaps=[]
for i in range(1,len(rows)):
    d=(rows[i][0]-rows[i-1][0]).total_seconds()
    if d>=1.0: gaps.append((d, rows[i-1], rows[i]))
gaps.sort(reverse=True)
if not gaps: print("(no gaps >=1s)")
else:
    for d,prev,cur in gaps[:10]:
        print(f"[gap {d:.3f}s] after {prev[1]} -> {cur[1]}")
        for lab in ("eml","path","action_type","case_id","file","component"):
            if lab in prev[2]: print("  prev:", lab, prev[2][lab])
            if lab in cur[2]:  print("  curr:", lab, cur[2][lab])
PY

# ---- 最後一批輸出與錯誤 ----
LATEST="$(ls -1dt reports_auto/e2e_mail/* 2>/dev/null | head -n1 || true)"
echo "[diag] LATEST: ${LATEST:-<none>}"
if [ -n "$LATEST" ]; then
  echo "---- SUMMARY.md ----"; sed -n '1,140p' "$LATEST/SUMMARY.md" 2>/dev/null || true
  echo "---- actions.jsonl (head) ----"; head -n 20 "$LATEST/actions.jsonl" 2>/dev/null || true
  echo "---- errors ----"
  if compgen -G "$LATEST/rpa_out/errors/*.err" > /dev/null; then
    for f in "$LATEST"/rpa_out/errors/*.err; do echo "-- $f --"; sed -n '1,80p' "$f"; done
  else
    echo "(none)"
  fi
fi

echo
echo "[diag] DONE. 重點檔案："
echo " - diag/import_trace.log        # import 流水（卡在誰一看就知道）"
echo " - diag/import_hang_tb.txt      # 卡住時的全執行緒堆疊"
echo " - diag/import_time.log         # importtime 概覽（若逾時則可能很短）"
