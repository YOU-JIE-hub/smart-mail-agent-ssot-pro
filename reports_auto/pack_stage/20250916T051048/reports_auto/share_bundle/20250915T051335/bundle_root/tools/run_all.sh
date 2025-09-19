#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$PWD}"
cd "$ROOT"
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"

ts(){ date +%Y%m%dT%H%M%S; }
TS="$(ts)"

echo "[DB] migrate/views/snapshot …"
python - <<'PY'
from __future__ import annotations
import sqlite3, csv, pathlib
DB = pathlib.Path("db/sma.sqlite"); DB.parent.mkdir(parents=True, exist_ok=True)
con = sqlite3.connect(DB); cur = con.cursor()
# 與 ActionBus 相容（TEXT 綁定安全）
cur.execute("""CREATE TABLE IF NOT EXISTS actions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT, intent TEXT, action TEXT, status TEXT,
  artifact_path TEXT, ext TEXT, message TEXT
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mail_id TEXT, ts TEXT, subject TEXT, body TEXT
)""")
# 視圖（先 drop 再建，SQLite 沒有 OR REPLACE）
cur.execute("DROP VIEW IF EXISTS v_intent_daily")
cur.execute("DROP VIEW IF EXISTS v_hitl_rate")
cur.execute("""
CREATE VIEW v_intent_daily AS
SELECT substr(ts,1,10) AS day, COALESCE(intent,'') AS intent, COUNT(*) AS n
FROM actions GROUP BY 1,2 ORDER BY 1 DESC, 3 DESC
""")
cur.execute("""
CREATE VIEW v_hitl_rate AS
WITH daily AS (
  SELECT substr(ts,1,10) AS day,
         COUNT(*) AS total,
         SUM(CASE WHEN COALESCE(intent,'')='' THEN 1 ELSE 0 END) AS hitl
  FROM actions GROUP BY 1
)
SELECT day,total,hitl, ROUND(CASE WHEN total>0 THEN 1.0*hitl/total ELSE 0 END,2) AS rate
FROM daily ORDER BY day DESC
""")
con.commit()
outdir = pathlib.Path("reports_auto/db_reports"); outdir.mkdir(parents=True, exist_ok=True)
rows = cur.execute("SELECT ts,intent,action,status,artifact_path FROM actions ORDER BY id DESC LIMIT 100").fetchall()
with open(outdir/"actions_tail.csv","w",newline="",encoding="utf-8") as f:
    csv.writer(f).writerows([["ts","intent","action","status","artifact_path"], *rows])
for name,sql,header in (
    ("v_intent_daily.csv","SELECT * FROM v_intent_daily ORDER BY day DESC, n DESC LIMIT 100",["day","intent","n"]),
    ("v_hitl_rate.csv","SELECT * FROM v_hitl_rate ORDER BY day DESC LIMIT 100",["day","total","hitl","rate"])
):
    try:
        rows = cur.execute(sql).fetchall()
        with open(outdir/name,"w",newline="",encoding="utf-8") as f:
            csv.writer(f).writerows([header,*rows])
    except Exception:
        pass
con.close()
print("[DB] done -> reports_auto/db_reports")
PY

echo "[TRI] run (只分類不落地動作)…"
python tools/tri_suite.py || true
LATEST_TRI="$(ls -t reports_auto/eval/*/tri_suite.json 2>/dev/null | head -n1 || true)"
if [ -n "$LATEST_TRI" ]; then
  echo "[TRI] $LATEST_TRI"; sed -n '1,120p' "$LATEST_TRI"
else
  echo "[TRI] no tri_suite.json"
fi

echo "[KIE] pick input and run…"
IN=""
if [ -s data/kie/test_real.jsonl ]; then IN=data/kie/test_real.jsonl
elif [ -s data/kie/test.jsonl ]; then IN=data/kie/test.jsonl
elif [ -s fixtures/eval_set.jsonl ]; then
  mkdir -p reports_auto/kie
  python - <<'PYX' < fixtures/eval_set.jsonl > reports_auto/kie/_from_fixtures.jsonl
import sys, json
for ln in sys.stdin:
    o=json.loads(ln); e=o.get("email",{})
    t=(e.get("subject","") + "\n" + e.get("body","")).strip()
    print(json.dumps({"text": t}, ensure_ascii=False))
PYX
  IN=reports_auto/kie/_from_fixtures.jsonl
fi
if [ -n "$IN" ]; then
  OUT="reports_auto/kie/pred_$(ts).jsonl"
  echo "[KIE] input: $IN"
  python tools/kie/eval.py "$IN" "$OUT" || true
  echo "[KIE] head:"; head -n 10 "$OUT" || true
else
  echo "[KIE] no input file found"
fi

echo "[BUNDLE] write env/db/tri/kie brief…"
python - <<'PY'
import os, sys, json, sqlite3, time, pathlib
TS=time.strftime("%Y%m%dT%H%M%S")
OUT=pathlib.Path(f"reports_auto/support_bundle/{TS}"); OUT.mkdir(parents=True, exist_ok=True)
def v(m):
    try: mod=__import__(m); return getattr(mod,"__version__","unknown")
    except Exception as e: return f"n/a ({type(e).__name__}: {e})"
def jdump(name, obj):
    p=OUT/name
    def default(o):
        try:
            import numpy as np
            if isinstance(o,(np.integer,)): return int(o)
            if isinstance(o,(np.floating,)): return float(o)
            if isinstance(o,(np.ndarray,)): return o.tolist()
        except Exception: pass
        return str(o)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=default), encoding="utf-8")
jdump("env.json",{
  "python": sys.version, "cwd": os.getcwd(),
  "numpy": v("numpy"), "sklearn": v("sklearn"), "joblib": v("joblib"),
  "transformers": v("transformers"), "torch": v("torch"),
  "env": {k:os.environ.get(k,"") for k in ("SMA_INTENT_ML_PKL","KIE_MODEL_DIR","TRANSFORMERS_OFFLINE")}
})
db="db/sma.sqlite"; info={"db":str(pathlib.Path(db).resolve()),"tables":[],"views":{}}
if pathlib.Path(db).exists():
    con=sqlite3.connect(db); cur=con.cursor()
    for t in ("actions","messages"):
        try: c=cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]; info["tables"].append({"name":t,"count":c})
        except Exception as e: info["tables"].append({"name":t,"error":str(e)})
    for name,sql,cols in (
        ("v_intent_daily","SELECT day,intent,n FROM v_intent_daily ORDER BY day DESC, n DESC LIMIT 20",["day","intent","n"]),
        ("v_hitl_rate","SELECT day,total,hitl,rate FROM v_hitl_rate ORDER BY day DESC LIMIT 20",["day","total","hitl","rate"])
    ):
        try:
            rows=cur.execute(sql).fetchall()
            info["views"][name]={"cols":cols,"rows":rows}
        except Exception as e:
            info["views"][name]={"error":str(e)}
    con.close()
jdump("db.json", info)
tri_latest=""
try:
    import glob
    pts=sorted(glob.glob("reports_auto/eval/*/tri_suite.json"), reverse=True)
    tri_latest=pts[0] if pts else ""
except Exception: pass
jdump("tri.json", {"latest":tri_latest})
kie_head=[]
try:
    import glob
    preds=sorted(glob.glob("reports_auto/kie/pred_*.jsonl"), reverse=True)
    if preds:
        with open(preds[0],"r",encoding="utf-8") as f:
            import itertools; kie_head=[next(f).strip() for _ in range(3)]
except Exception: pass
jdump("kie.json", {"pred_head": kie_head})
print(json.dumps({"bundle": str(OUT)}, ensure_ascii=False))
PY

echo
echo "[DONE] 查看產物："
echo " - reports_auto/db_reports/"
echo " - reports_auto/eval/<TS>/tri_suite.json"
echo " - reports_auto/kie/pred_*.jsonl"
echo " - reports_auto/support_bundle/<TS>/"

python tools/spam_report.py || true

python tools/support_bundle.py || true
