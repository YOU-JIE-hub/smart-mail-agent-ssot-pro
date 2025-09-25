from __future__ import annotations
from pathlib import Path
import json, glob, os, datetime as dt, sqlite3, statistics, re

def iso(s): 
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
def load_events(ev_dir="reports_auto/events"):
    rows=[]
    for fp in sorted(glob.glob(f"{ev_dir}/*.ndjson")):
        with open(fp,"r",encoding="utf-8") as f:
            for ln in f:
                ln=ln.strip()
                if not ln: continue
                try: rows.append(json.loads(ln))
                except Exception: pass
    return rows

def daily_kpi(rows):
    by={}
    for r in rows:
        d=(r.get("run_ts") or "")[:8]; 
        if not d: continue
        by.setdefault(d, {"runs":0,"e2e_done":0,"hil_blocked":0,"sent":0})
        if r.get("action")=="e2e_start": by[d]["runs"]+=1
        if r.get("action")=="e2e_done": by[d]["e2e_done"]+=1
        if r.get("action")=="hil_blocked": by[d]["hil_blocked"]+=r.get("moved",0) or 0
        if r.get("action")=="send_email": by[d]["sent"]+=1
    return by

def latency(rows):
    # per-run: e2e_start -> e2e_done seconds
    t={}
    for r in rows:
        a=r.get("action"); rt=r.get("run_ts"); ts=r.get("ts")
        if not (rt and ts): continue
        if a=="e2e_start": t.setdefault(rt, {})["s"]=ts
        if a=="e2e_done":  t.setdefault(rt, {})["e"]=ts
    vals=[]
    for rt,p in t.items():
        if "s" in p and "e" in p:
            vals.append((rt, (iso(p["e"]) - iso(p["s"])).total_seconds()))
    dist={"count":len(vals),"p50":None,"p95":None}
    if vals:
        arr=[v for _,v in vals]
        arr_sorted=sorted(arr)
        def pct(p): 
            k=max(0, int(round((p/100)*(len(arr_sorted)-1))))
            return arr_sorted[k]
        dist["p50"]=pct(50); dist["p95"]=pct(95)
    return vals, dist

def top_errors(rows, topn=5):
    cnt={}
    for r in rows:
        if r.get("result")=="fail":
            k=r.get("err_type") or "unknown"
            cnt[k]=cnt.get(k,0)+1
    return sorted(cnt.items(), key=lambda x:-x[1])[:topn]

def db_overview(db="db/sma.sqlite"):
    total=succeeded=emails=0
    if Path(db).exists():
        con=sqlite3.connect(db); cur=con.cursor()
        try:
            total=cur.execute("select count(1) from actions").fetchone()[0]
            succeeded=cur.execute("select count(1) from actions where status='succeeded'").fetchone()[0]
            emails=cur.execute("select count(1) from actions where action='SendEmail' and status='succeeded'").fetchone()[0]
        except Exception: pass
        con.close()
    return total,succeeded,emails

def pending_hint(db="db/sma.sqlite", run_root="reports_auto/e2e_mail"):
    pending=0
    if Path(db).exists():
        con=sqlite3.connect(db); cur=con.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS approvals(run_ts TEXT, case_id TEXT, approved_by TEXT, approved_at TEXT)")
        con.close()
    # 粗略提示：blocked 檔案數即代表待核准
    for p in Path(run_root).glob("*/rpa_out/email_blocked/*.txt"):
        pending+=1
    return pending

def build():
    rows=load_events()
    daily=daily_kpi(rows); vals,dist=latency(rows); errs=top_errors(rows)
    total,succ,emails=db_overview()
    pend=pending_hint()
    html=["<html><head><meta charset='utf-8'><title>SMA 運行儀表板</title>",
          "<style>body{font-family:ui-sans-serif,system-ui;max-width:1100px;margin:20px auto}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ddd;padding:8px;text-align:left}</style>",
          "</head><body><h1>SMA 運行儀表板</h1>"]
    # 每日 KPI
    html.append("<h2>每日 KPI</h2><table><thead><tr><th>日期</th><th>runs</th><th>e2e_done</th><th>hil_blocked</th><th>sent</th></tr></thead><tbody>")
    for d in sorted(daily):
        k=daily[d]; html.append(f"<tr><td>{d}</td><td>{k['runs']}</td><td>{k['e2e_done']}</td><td>{k['hil_blocked']}</td><td>{k['sent']}</td></tr>")
    html.append("</tbody></table>")
    # 事件分佈
    from collections import Counter
    c=Counter([r.get("action") for r in rows if r.get("action")])
    html.append("<h2>事件分佈</h2><table><thead><tr><th>action</th><th>count</th></tr></thead><tbody>")
    for k,v in sorted(c.items(), key=lambda x:-x[1]): html.append(f"<tr><td>{k}</td><td>{v}</td></tr>")
    html.append("</tbody></table>")
    # 延遲分佈
    html.append("<h2>延遲分佈</h2>")
    html.append(f"<p>樣本數={dist['count']}，p50={dist['p50']}s，p95={dist['p95']}s</p>")
    # 錯誤 TopN
    html.append("<h2>錯誤 TopN</h2><table><thead><tr><th>err_type</th><th>count</th></tr></thead><tbody>")
    for k,v in errs: html.append(f"<tr><td>{k}</td><td>{v}</td></tr>")
    html.append("</tbody></table>")
    # DB 概覽 + 待核准提示
    html.append("<h2>DB 概覽</h2><pre>")
    html.append(f"actions_total: {total}\nactions_succeeded: {succ}\nemails_sent: {emails}\n")
    html.append(f"pending_approvals (估算 by blocked/*.txt): {pend}\n</pre>")
    html.append("<p style='color:#999'>檔案位置：reports_auto/dashboard/index.html</p></body></html>")
    out=Path("reports_auto/dashboard/index.html"); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(html), encoding="utf-8")
    print("[OK] dashboard ->", out)
if __name__=="__main__": build()
