
from __future__ import annotations
import json, sqlite3, time
from pathlib import Path
from tools.pipeline_ml import classify_ml

DB = Path("db/sma.sqlite"); DB.parent.mkdir(parents=True, exist_ok=True)

def main():
    # 資料來源：fixtures/eval_set.jsonl（若無，使用 6 條內建樣本）
    items=[]
    f=Path("fixtures/eval_set.jsonl")
    if f.exists():
        for ln in f.read_text(encoding="utf-8").splitlines():
            o=json.loads(ln); items.append(o.get("email",{}))
    else:
        items = [
          {"subject":"[一般回覆] 測試","body":"hello"},
          {"subject":"報價 請提供 單價:100 數量:2","body":""},
          {"subject":"投訴","body":"客訴"},
          {"subject":"技術支援 ticket:TS-1234","body":""},
          {"subject":"請問規則","body":"這是規則詢問"},
          {"subject":"修改我的地址","body":"新的地址在…"},
        ]
    con=sqlite3.connect(DB); cur=con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS actions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts TEXT, intent TEXT, action TEXT, status TEXT,
      artifact_path TEXT, ext TEXT, message TEXT
    )""")
    now = time.strftime("%Y%m%dT%H%M%S")
    for e in items:
        res = classify_ml(e)
        if isinstance(res, tuple) and len(res)==3:
            zh, conf, raw = res
        else:
            zh, conf = res
            raw = {"top1": zh, "conf": conf}
        # top2（若可）與 margin
        top2 = raw.get("top2")
        margin = None
        if "proba" in raw and isinstance(raw["proba"], list) and len(raw["proba"])>=2:
            ps=sorted(raw["proba"], reverse=True); margin=float(ps[0]-ps[1])
        ext={"ml_top1": zh, "ml_conf": conf, "ml_top2": top2, "ml_margin": margin, "raw": raw}
        cur.execute("INSERT INTO actions(ts,intent,action,status,artifact_path,ext,message) VALUES(?,?,?,?,?,?,?)",
                    (now, "", "ml_signal","ok","", json.dumps(ext,ensure_ascii=False), json.dumps(e,ensure_ascii=False)))
    con.commit(); con.close()
    print("[ML] logged weak-signals -> actions")
if __name__ == "__main__":
    main()
