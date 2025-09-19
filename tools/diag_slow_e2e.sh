#!/usr/bin/env bash
set -Eeuo pipefail

PROJ="${PROJ:-$HOME/projects/smart-mail-agent_ssot}"
EMLDIR="${EMLDIR:-data/demo_eml}"
TIMEOUT="${TIMEOUT:-240}"
HEARTBEAT_INT="${HEARTBEAT_INT:-0.5}"

cd "$PROJ"
mkdir -p diag

# ---- venv & 環境 ----
python3 -m venv .venv 2>/dev/null || true
. .venv/bin/activate
export PYTHONUNBUFFERED=1 PYTHONFAULTHANDLER=1
export PYTHONPATH="$PROJ/src:${PYTHONPATH:-}"

# 清理 .pth，只留 src；移除任何 import usercustomize
SP="$(python - <<'PY'
import sysconfig
print(sysconfig.get_paths().get("purelib") or sysconfig.get_paths().get("platlib"))
PY
)"
printf '%s\n' "$PROJ/src" > "$SP/zzz_sma_root.pth"
shopt -s nullglob
for p in "$SP"/*.pth; do sed -i '/import[[:space:]]\+usercustomize/d' "$p" || true; done

# ---- 基本健康檢查 ----
echo "[diag] artifacts & sizes"
ls -lh artifacts_prod 2>/dev/null || true
for f in artifacts_prod/model_pipeline.pkl artifacts_prod/ens_thresholds.json artifacts_prod/intent_rules_calib_v11c.json; do
  [ -f "$f" ] && echo "  - $f $(stat -c %s "$f" 2>/dev/null) bytes" || echo "  - MISSING: $f"
done

echo "[diag] sqlite schema (brief)"
python - <<'PY'
import sqlite3, os
os.makedirs("db", exist_ok=True)
conn = sqlite3.connect("db/sma.sqlite")
cur = conn.cursor()
# 基表
cur.execute("CREATE TABLE IF NOT EXISTS actions (id TEXT PRIMARY KEY, case_id TEXT, action_type TEXT, path TEXT, created_at TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS intent_preds (case_id TEXT)")
# 補欄位（避免變數蓋掉）
def ensure(table, col, ddl):
    cols=[r[1] for r in cur.execute(f"PRAGMA table_info({table})")]
    if col not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
for table,col,ddl in [
    ("intent_preds","label","TEXT"),("intent_preds","confidence","REAL"),("intent_preds","created_at","TEXT"),
    ("kie_spans","case_id","TEXT"),("kie_spans","key","TEXT"),("kie_spans","value","TEXT"),("kie_spans","start","INT"),("kie_spans","end","INT"),
    ("err_log","ts","TEXT"),("err_log","case_id","TEXT"),("err_log","err","TEXT"),
]:
    try: ensure(table,col,ddl)
    except Exception: pass
for t in ("intent_preds","actions","kie_spans","err_log"):
    try: print(t, [r[1] for r in cur.execute(f"PRAGMA table_info({t})")])
    except Exception as e: print(t, "err:", e)
conn.commit(); conn.close()
PY

# ---- 匯入耗時（import graph）----
echo "[diag] python -X importtime (import 開銷)"
python -X importtime -c 'import smart_mail_agent.cli.e2e' 2> diag/import_time.log || true
tail -n 30 diag/import_time.log || true

# ---- 選擇入口 ----
if python - <<'PY' 2>/dev/null; then
import importlib; importlib.import_module("smart_mail_agent.cli.e2e"); print("OK")
PY
then
  CMD=(python -u -m smart_mail_agent.cli.e2e "$EMLDIR")
else
  CMD=(python -u scripts/sma_e2e_mail.py "$EMLDIR")
fi
echo "[diag] CMD: ${CMD[*]}"

# ---- strace（若存在） + 心跳 + 逾時 ----
USE_STRACE=0
if command -v strace >/dev/null 2>&1; then USE_STRACE=1; fi

if [ "$USE_STRACE" -eq 1 ]; then
  echo "[diag] strace enabled (file,network,process,signal)"
  ( timeout "$TIMEOUT" strace -f -tt -T -s 256 -o diag/strace.txt -e trace=file,network,process,signal -- "${CMD[@]}" ) & pid=$!
else
  echo "[diag] strace NOT found; running plain"
  ( timeout "$TIMEOUT" "${CMD[@]}" ) & pid=$!
fi

start=$(date +%s)
while kill -0 "$pid" 2>/dev/null; do
  printf "\r[hb] running... %3ds " $(( $(date +%s) - start ))
  sleep "$HEARTBEAT_INT"
done
echo
wait "$pid" || true
RC=$?
echo "[diag] rc=$RC"

# ---- 連線/鎖 檢查 ----
echo "[diag] network sockets (python)"
if command -v ss >/dev/null 2>&1; then ss -tpn | grep -i python || true; else netstat -tpn 2>/dev/null | grep -i python || true; fi

echo "[diag] sqlite lsof"
if command -v lsof >/dev/null 2>&1; then lsof db/sma.sqlite || true; else echo "(lsof not installed)"; fi

# ---- NDJSON gap 分析（找最大卡點）----
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
            j=json.loads(line)
            ts=j.get("ts") or j.get("timestamp")
            k=j.get("kind") or j.get("event") or j.get("phase")
            rows.append((ts,k,j))
        except Exception:
            pass
def to_dt(s):
    try: return dt.datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(dt.timezone.utc)
    except Exception: return None
rows=[(to_dt(ts),k,j) for ts,k,j in rows if to_dt(ts)]
rows.sort(key=lambda x:x[0])
gaps=[]
for i in range(1,len(rows)):
    delta=(rows[i][0]-rows[i-1][0]).total_seconds()
    if delta>=1.0:
        gaps.append((delta, rows[i-1], rows[i]))
gaps.sort(reverse=True)
top=gaps[:10]
if not top:
    print("(no gaps >=1s)")
else:
    for d,prev,cur in top:
        print(f"[gap {d:.3f}s] after {prev[1]} -> {cur[1]}")
        pj=prev[2]; cj=cur[2]
        for lab in ("eml","path","action_type","case_id","file","component"):
            if lab in pj: print("  prev:", lab, pj[lab])
            if lab in cj: print("  curr:", lab, cj[lab])
PY

# ---- strace 聚合（哪類 syscall 最花時間）----
if [ "$USE_STRACE" -eq 1 ] && [ -s diag/strace.txt ]; then
  echo "[diag] strace top syscalls by time"
  awk '
    /</ {
      if (match($0, /<([0-9]+\.[0-9]+)>/, m)) tm=m[1]; else tm="";
      name="";
      if (match($0, /[0-9:.]+\s+[0-9]+\s+([a-z_]+)\(/, n)) name=n[1];
      else if (match($0, /([a-z_]+)\(/, n)) name=n[1];
      if (tm!="" && name!="") sum[name]+=tm;
    }
    END { for (k in sum) printf("%10.3fs  %s\n", sum[k], k) | "sort -nr" }
  ' diag/strace.txt | head -n 20 || true

  echo "[diag] strace notable calls (connect/open/recv/send) last 40"
  egrep -n ' connect\(| open\(| read\(| write\(| recv\(| send\(' diag/strace.txt | tail -n 40 || true
fi

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
