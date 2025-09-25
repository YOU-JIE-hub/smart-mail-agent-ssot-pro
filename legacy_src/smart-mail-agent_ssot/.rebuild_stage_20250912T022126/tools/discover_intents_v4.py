from __future__ import annotations
import os, re, json, glob, sqlite3, argparse
from pathlib import Path
ROOT=Path(".")

NOISE={s.lower() for s in """
__class__,ok,fail,skip,test,demo,send_email,outbox_only,deny_whitelist,
planned,running,succeeded,failed,downgraded,skipped_by_hil,
change_draft,ticket_create,do_quarantine,manual_triage,faq_answer,quarantine,
action,attachments,case_id,confidence,db,id,idem,idempotency_key,inline,intent,
intent_conf,intent_label,label,level,other,preconditions,pred,result,rules,runner,
steps,subject_tag,tools,type,utf-8,version,INFO,final,faq_embed,faq_embed_done,faq_embed_skip,
SendEmail
""".replace("\n","").split(",") if s.strip()}
UUID=re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

def tok_ok(s:str)->bool:
    s=s.strip()
    if not s or len(s)>40: return False
    if UUID.match(s): return False
    if s.lower() in NOISE: return False
    if not re.search(r"[A-Za-z0-9\u4e00-\u9fa5]", s): return False
    return True

def extract(o)->set[str]:
    out=set()
    if isinstance(o, dict):
        for k in ("intents","labels"):
            v=o.get(k)
            if isinstance(v,(list,tuple)):
                for x in v:
                    if isinstance(x,str): out.add(x.strip())
        if isinstance(o.get("rules"),(list,tuple)):
            for r in o["rules"]:
                it=r.get("intent")
                if isinstance(it,str): out.add(it.strip())
        for k in ("intent_map","intent_rules","label_map"):
            v=o.get(k)
            if isinstance(v,dict):
                for k2 in v.keys():
                    if isinstance(k2,str): out.add(k2.strip())
    elif isinstance(o,list):
        for r in o:
            if isinstance(r,dict) and isinstance(r.get("intent"),str):
                out.add(r["intent"].strip())
            elif isinstance(r,str):
                out.add(r.strip())
    return out

def from_artifacts()->set[str]:
    names=set()
    pats=["artifacts_prod/*intent*.json","artifacts_prod/intent_rules*.json",
          "artifacts_prod/*.rules.json","artifacts_prod/*.labels.json"]
    for pat in pats:
        for p in ROOT.glob(pat):
            try:
                obj=json.loads(p.read_text("utf-8",errors="ignore"))
            except Exception:
                continue
            names |= extract(obj)
    return {x for x in names if tok_ok(x)}

def from_code()->set[str]:
    names=set()
    pat_str=re.compile(r'["\']([A-Za-z0-9_\-\u4e00-\u9fa5]{2,40})["\']')
    pat_ctx=re.compile(r'\bintent\b|\b意圖\b', re.I)
    paths=set()
    for g in ["src/**/*intent*.py","src/**/*Intent*.py","src/**/*.json","src/**/*.yaml","src/**/*.yml","tools/**/*.py","configs/**/*.json","configs/**/*.yaml","configs/**/*.yml"]:
        paths |= set(ROOT.glob(g))
    for p in paths:
        try: t=p.read_text("utf-8",errors="ignore")
        except Exception: continue
        if p.suffix.lower() not in (".json",".yaml",".yml") and not pat_ctx.search(t):
            continue
        for m in pat_str.finditer(t):
            s=m.group(1).strip()
            ctx=t[max(0,m.start()-80):m.end()+80]
            if pat_ctx.search(ctx) and tok_ok(s):
                names.add(s)
    return names

def from_ndjson()->set[str]:
    names=set()
    for fp in sorted(ROOT.glob("reports_auto/events/*.ndjson")):
        try:
            with fp.open("r",encoding="utf-8") as f:
                for ln in f:
                    if not ln.startswith("{"): continue
                    try: obj=json.loads(ln)
                    except Exception: continue
                    it=obj.get("intent")
                    if isinstance(it,str) and tok_ok(it):
                        names.add(it.strip())
        except Exception: pass
    return names

def from_outbox()->set[str]:
    names=set()
    for txt in ROOT.glob("reports_auto/e2e_mail/*/rpa_out/email_outbox/*.txt"):
        it=txt.stem
        if tok_ok(it): names.add(it)
    return names

def from_db()->set[str]:
    names=set()
    db=ROOT/"db"/"sma.sqlite"
    if not db.exists(): return names
    try:
        con=sqlite3.connect(db); cur=con.cursor()
        tbls=[r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for t in tbls:
            cols=[r[1] for r in cur.execute(f"PRAGMA table_info({t})")]
            if "intent" in cols:
                for (v,) in cur.execute(f"SELECT DISTINCT intent FROM {t} WHERE intent IS NOT NULL AND TRIM(intent)<>''"):
                    if isinstance(v,str) and tok_ok(v): names.add(v.strip())
    except Exception: pass
    finally:
        try: con.close()
        except Exception: pass
    return names

def from_override(path)->list[str]:
    p=ROOT/path
    if not p.exists(): return []
    out=[]
    for ln in p.read_text("utf-8",errors="ignore").splitlines():
        s=ln.strip()
        if s and not s.startswith("#") and tok_ok(s):
            out.append(s)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--override", default="configs/intent_names_override.txt")
    ap.add_argument("--names-out", default="artifacts_prod/intent_names.json")
    ap.add_argument("--report", default=None)
    args=ap.parse_args()

    a=from_artifacts(); b=from_code(); c=from_ndjson(); d=from_outbox(); e=from_db(); o=from_override(args.override)
    sources={"artifacts":a,"code":b,"ndjson":c,"outbox":d,"db":e}

    # 合併策略：若 override 有內容，直接採用；否則取 override 預設序列缺的補齊到 6
    prefs=["一般回覆","報價","投訴","技術支援","規則詢問","資料異動"]
    votes={}
    for label, s in sources.items():
        for name in s:
            votes.setdefault(name, set()).add(label)

    override=[x for x in o if tok_ok(x)]
    if override:
        final=override[:6]
    else:
        chosen=[p for p in prefs if p in votes]
        rest=[n for n in votes.keys() if n not in chosen]
        final=(chosen+rest)[:6]

    Path(args.names_out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.names_out,"w",encoding="utf-8") as w:
        json.dump({"version":"v1","names": final, "detected_counts":{k:len(v) for k,v in sources.items()}}, w, ensure_ascii=False, indent=2)

    if args.report:
        with open(args.report,"w",encoding="utf-8") as w:
            w.write("# Intent Names (v4)\n\n")
            w.write(f"- detected_counts: { {k:len(v) for k,v in sources.items()} }\n")
            w.write(f"- names: {', '.join(final) if final else '(none)'}\n")

    print(f"[OK] names -> {args.names_out}  N={len(final)}")

if __name__=="__main__":
    main()
