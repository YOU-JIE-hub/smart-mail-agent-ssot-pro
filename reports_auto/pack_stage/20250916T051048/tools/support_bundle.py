
from __future__ import annotations
import sys, os, json, time, sqlite3
from pathlib import Path

def safe_version(mod:str)->str:
    try:
        m=__import__(mod); return getattr(m,"__version__","unknown")
    except Exception as e:
        return f"n/a ({type(e).__name__}: {e})"

TS=time.strftime("%Y%m%dT%H%M%S")
OUTDIR=Path(f"reports_auto/support_bundle/{TS}")
OUTDIR.mkdir(parents=True, exist_ok=True)

env = {
    "python": sys.version,
    "cwd": str(Path.cwd()),
    "numpy": safe_version("numpy"),
    "sklearn": safe_version("sklearn"),
    "joblib": safe_version("joblib"),
    "transformers": safe_version("transformers"),
    "torch": safe_version("torch"),
    "env": {k:os.environ.get(k,"") for k in ("SMA_INTENT_ML_PKL","KIE_MODEL_DIR","TRANSFORMERS_OFFLINE")}
}
(OUTDIR/"env.json").write_text(json.dumps(env,ensure_ascii=False,indent=2),encoding="utf-8")

# DB 摘要
dbp=Path("db/sma.sqlite")
if dbp.exists():
    con=sqlite3.connect(dbp); cur=con.cursor()
    def q(sql): 
        try:
            cur.execute(sql); 
            cols=[d[0] for d in cur.description]; rows=cur.fetchall()
            return {"cols":cols,"rows":rows}
        except Exception as e:
            return {"error": str(e)}
    dump={
      "tables":[{"name":t[0],"count":cur.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]} 
                for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()],
      "v_intent_daily": q("SELECT * FROM v_intent_daily ORDER BY day DESC, n DESC LIMIT 10"),
      "v_hitl_rate": q("SELECT * FROM v_hitl_rate ORDER BY day DESC LIMIT 10")
    }
    con.close()
    (OUTDIR/"db_summary.json").write_text(json.dumps(dump,ensure_ascii=False,indent=2),encoding="utf-8")

print(json.dumps({"bundle": str(OUTDIR)}, ensure_ascii=False))
