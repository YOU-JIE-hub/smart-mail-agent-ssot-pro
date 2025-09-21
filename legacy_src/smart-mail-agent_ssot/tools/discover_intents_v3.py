from __future__ import annotations
import os, re, json, glob, sqlite3
from pathlib import Path
ROOT=Path(".")

# ===== 來源 1：Artifacts（最高優先）=====
ART_GLOBS=[
    "artifacts_prod/*intent*.json",
    "artifacts_prod/intent_rules*.json",
    "artifacts_prod/*.rules.json",
    "artifacts_prod/*.labels.json",
]
def from_artifacts()->set[str]:
    names=set()
    paths=[]
    for g in ART_GLOBS:
        paths+=list(ROOT.glob(g))
    for p in paths:
        try:
            obj=json.loads(p.read_text("utf-8",errors="ignore"))
        except Exception:
            continue
        names |= extract_names(obj)
    return names

def extract_names(obj)->set[str]:
    out=set()
    if isinstance(obj, dict):
        # 常見結構
        for k in ("intents","labels"):
            v=obj.get(k)
            if isinstance(v,(list,tuple)):
                for x in v:
                    if isinstance(x,str): out.add(x.strip())
        if isinstance(obj.get("rules"),(list,tuple)):
            for r in obj["rules"]:
                it=r.get("intent")
                if isinstance(it,str): out.add(it.strip())
        for k in ("intent_map","intent_rules","label_map"):
            v=obj.get(k)
            if isinstance(v,dict):
                for k2 in v.keys():
                    if isinstance(k2,str): out.add(k2.strip())
    elif isinstance(obj,list):
        for r in obj:
            if isinstance(r,dict) and isinstance(r.get("intent"),str):
                out.add(r["intent"].strip())
            elif isinstance(r,str):
                out.add(r.strip())
    return out

# ===== 來源 2：原始碼（Python/JSON/YAML）=====
CODE_GLOBS=[
    "src/**/*intent*.py","src/**/*Intent*.py",
    "src/**/*.json","src/**/*.yaml","src/**/*.yml",
    "configs/**/*.json","configs/**/*.yaml","configs/**/*.yml",
    "tools/**/*.py",
]
NOISE=set(x.lower() for x in
    ["__class__","ok","fail","skip","test","demo","send_email","outbox_only","deny_whitelist",
     "planned","running","succeeded","failed","downgraded","skipped_by_hil",
     "change_draft","ticket_create","do_quarantine","manual_triage","faq_answer","quarantine"]
)
def from_code()->set[str]:
    names=set()
    paths=set()
    for pat in CODE_GLOBS:
        paths |= set(Path().glob(pat))
    str_pat=re.compile(r'["\']([A-Za-z0-9_\-\u4e00-\u9fa5]{2,40})["\']')
    key_pat=re.compile(r'\bintent\b|\b意圖\b', re.I)
    for p in paths:
        try:
            t=p.read_text("utf-8",errors="ignore")
        except Exception:
            continue
        if not key_pat.search(t) and p.suffix.lower() not in (".json",".yaml",".yml"):
            continue
        for m in str_pat.finditer(t):
            s=m.group(1).strip()
            if not s: continue
            # 上下文含 intent/意圖 才收
            ctx=t[max(0,m.start()-80):m.end()+80]
            if key_pat.search(ctx):
                if s.lower() not in NOISE:
                    names.add(s)
    return names

# ===== 來源 3：NDJSON 事件 =====
def from_ndjson()->set[str]:
    names=set()
    for fp in sorted(ROOT.glob("reports_auto/events/*.ndjson")):
        try:
            with fp.open("r",encoding="utf-8") as f:
                for ln in f:
                    ln=ln.strip()
                    if not ln or ln[:1] != "{": continue
                    try: obj=json.loads(ln)
                    except Exception: continue
                    it=obj.get("intent")
                    if isinstance(it,str) and it.strip():
                        if it.lower() not in NOISE:
                            names.add(it.strip())
        except Exception:
            continue
    return names

# ===== 來源 4：OUTBOX 檔名 =====
def from_outbox()->set[str]:
    names=set()
    for txt in ROOT.glob("reports_auto/e2e_mail/*/rpa_out/email_outbox/*.txt"):
        it=txt.stem.split("_")[-1]
        if 2<=len(it)<=40 and it.lower() not in NOISE:
            names.add(it)
    return names

# ===== 來源 5：DB（找任何含 intent 欄位的表；否則略過）=====
def from_db()->set[str]:
    names=set()
    db=ROOT/"db"/"sma.sqlite"
    if not db.exists(): return names
    try:
        con=sqlite3.connect(db)
        cur=con.cursor()
        # 掃有 intent 欄位的表
        tables=[r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for t in tables:
            cols=[r[1] for r in cur.execute(f"PRAGMA table_info({t})")]
            if "intent" in cols:
                for (val,) in cur.execute(f"SELECT DISTINCT intent FROM {t} WHERE intent IS NOT NULL AND TRIM(intent)<>''"):
                    if isinstance(val,str) and val.strip() and val.lower() not in NOISE:
                        names.add(val.strip())
    except Exception:
        pass
    finally:
        try: con.close()
        except Exception: pass
    return names

# ===== 來源 6：手動 override（若存在）=====
def from_override()->set[str]:
    p=ROOT/"configs"/"intent_names_override.txt"
    if not p.exists(): return set()
    out=set()
    for ln in p.read_text("utf-8",errors="ignore").splitlines():
        s=ln.strip()
        if s and not s.startswith("#") and s.lower() not in NOISE:
            out.add(s)
    return out

def normalize(names:set[str])->list[str]:
    def ok(s:str)->bool:
        if not s: return False
        if len(s)>40: return False
        if s.startswith("__") and s.endswith("__"): return False
        return True
    cleaned={re.sub(r'\s+',' ',s).strip() for s in names if ok(s)}
    # 英文先、中文後，穩定排序
    return sorted(cleaned, key=lambda x:(re.match(r'^[\u4e00-\u9fa5]',x) is not None, x.lower()))

def main():
    a=from_artifacts()
    b=from_code()
    c=from_ndjson()
    d=from_outbox()
    e=from_db()
    o=from_override()
    # 決策：Artifacts 若非空，以它為核心，再合併其餘來源（但不會被噪音覆蓋）
    base = a if a else set()
    union = (base | b | c | d | e | o)
    names = normalize(union)
    print(json.dumps({
        "counts":{"artifacts":len(a),"code":len(b),"ndjson":len(c),"outbox":len(d),"db":len(e),"override":len(o)},
        "intents": names
    }, ensure_ascii=False, indent=2))
if __name__=="__main__":
    main()
