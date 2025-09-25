from __future__ import annotations
import json, re, glob, os
from pathlib import Path
ROOT=Path(".")
ARTS=list(ROOT.glob("artifacts_prod/*intent*.json")) + list(ROOT.glob("artifacts_prod/intent_rules*.json"))
SEND=ROOT/"tools"/"send_with_intent_attachments.py"
TEST_NOISE={"__class__","ok","fail","skip","test","demo","send_email","outbox_only","deny_whitelist"}

def from_artifacts()->set[str]:
    intents=set()
    for p in ARTS:
        try:
            obj=json.loads(p.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        # 可能出現的位置
        if isinstance(obj, dict):
            if "intents" in obj and isinstance(obj["intents"], (list,tuple)):
                for x in obj["intents"]:
                    if isinstance(x, str): intents.add(x.strip())
            if "rules" in obj and isinstance(obj["rules"], (list,tuple)):
                for r in obj["rules"]:
                    it=r.get("intent")
                    if isinstance(it, str): intents.add(it.strip())
            # 有些規則直接以 key 命名
            for k in ("intent_map","intent_rules","labels"):
                v=obj.get(k)
                if isinstance(v, dict):
                    for k2 in v.keys():
                        if isinstance(k2,str): intents.add(k2.strip())
        elif isinstance(obj, list):
            for r in obj:
                if isinstance(r, dict) and isinstance(r.get("intent"), str):
                    intents.add(r["intent"].strip())
    return {i for i in intents if i}

def from_sender()->set[str]:
    # 只有當 artifacts 完全挖不到時才使用
    if not SEND.exists(): return set()
    t=SEND.read_text(encoding="utf-8", errors="ignore")
    intents=set()
    for m in re.finditer(r'["\']([A-Za-z0-9_\-\u4e00-\u9fa5]{2,40})["\']', t):
        s=m.group(1)
        ctx=t[max(0,m.start()-60):m.end()+60]
        if re.search(r'(intent|Generate|Create|Ticket|Quote|Diff|FAQ|Reply|工單|報價|差異|隔離|封鎖)', ctx, re.I):
            intents.add(s)
    return intents

def from_outbox()->set[str]:
    intents=set()
    for txt in ROOT.glob("reports_auto/e2e_mail/*/rpa_out/email_outbox/*.txt"):
        name=txt.stem
        # 常見命名：<case>_<IntentName>；保守取尾段
        if "_" in name:
            it=name.split("_")[-1]
            if 2<=len(it)<=40: intents.add(it)
    return intents

def normalize(names:set[str])->list[str]:
    cleaned=set()
    for s in names:
        s=re.sub(r'\s+',' ',s).strip().strip("[](){}")
        if not s: continue
        if s.startswith("__") and s.endswith("__"):  # 排除 dunder
            continue
        if len(s)>40: continue
        cleaned.add(s)
    return sorted(cleaned, key=lambda x:(re.match(r'^[\u4e00-\u9fa5]',x) is not None, x.lower()))

def main():
    a=from_artifacts()
    # 如果 artifacts 有資料，就以它為唯一真相；否則再加上 sender/outbox 的推測，並剔除常見噪音
    if a:
        all_names=normalize(a)
    else:
        b=from_sender(); c=from_outbox()
        cand=(b|c) - TEST_NOISE
        all_names=normalize(cand)
    print(json.dumps({"intents": all_names}, ensure_ascii=False))
if __name__=="__main__":
    main()
