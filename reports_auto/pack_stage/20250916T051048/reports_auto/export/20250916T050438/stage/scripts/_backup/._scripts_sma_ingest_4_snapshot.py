import argparse, json
from pathlib import Path
MAP_INTENT_EN2ZH={"biz_quote":"報價","tech_support":"技術支援","complaint":"投訴","policy_qa":"規則詢問","profile_update":"資料異動","other":"其他"}
def write_jsonl(p, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p,"w",encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False)+"\n")
def ingest_spam(src, dst):
    sp = src/"4"/"all.jsonl"
    if not sp.exists(): return 0
    rows=[]
    for ln in sp.read_text("utf-8").splitlines():
        if not ln.strip(): continue
        o=json.loads(ln)
        txt=o.get("text") or ((o.get("subject","")+"\n"+o.get("body","")).strip())
        rows.append({"text":txt, "spam": 1 if o.get("label")=="spam" else 0})
    out=dst/"spam_eval"/"dataset.jsonl"; write_jsonl(out, rows); return len(rows)
def ingest_intent(src, dst):
    rows=[]; cands=["i_demo.jsonl","demo_intent.jsonl","i_20250901_full.jsonl"]
    for name in cands:
        p=src/"4"/name
        if p.exists():
            for ln in p.read_text("utf-8").splitlines():
                if not ln.strip(): continue
                o=json.loads(ln)
                txt=o.get("text") or ((o.get("subject","")+"\n"+o.get("body","")).strip())
                lab=o.get("label"); lab=MAP_INTENT_EN2ZH.get(lab,lab)
                rows.append({"text":txt,"intent":lab})
    if rows:
        out=dst/"intent_eval"/"dataset.jsonl"; write_jsonl(out, rows); return len(rows)
    return 0
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--src",required=True); ap.add_argument("--dst",default="data")
    a=ap.parse_args(); src=Path(a.src); dst=Path(a.dst)
    ns=ingest_spam(src,dst); ni=ingest_intent(src,dst)
    print(f"[OK] ingest spam={ns} intent={ni}")
if __name__=="__main__": main()
