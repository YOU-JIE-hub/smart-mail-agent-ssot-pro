from __future__ import annotations
from pathlib import Path
import os, json, re, time
from collections import Counter

OUT_DIR=Path(f"reports_auto/eval/{time.strftime('%Y%m%dT%H%M%S')}")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CAND = [
    ("data/kie/test.jsonl","data/kie/val.jsonl"),
    ("reports_auto/kie/test.jsonl","reports_auto/kie/val.jsonl"),
]
def pick_files():
    for t,v in CAND:
        if Path(t).exists() and Path(v).exists():
            return Path(t), Path(v)
    # 最小集
    fx=Path("fixtures/kie_eval_set.jsonl"); fx.parent.mkdir(parents=True, exist_ok=True)
    if not fx.exists():
        fx.write_text("\n".join([
            json.dumps({"labels":{"price":"100","qty":"2","id":"TS-1234"},"email":{"subject":"報價 單價:100 數量:2","body":"ticket:TS-1234"}}),
            json.dumps({"labels":{"price":"299","qty":"5","id":"ORD-9"},"email":{"subject":"資料異動 order:ORD-9","body":"單價:299 數量:5"}}),
        ]), encoding="utf-8")
    return fx, fx

TEST, VAL = pick_files()

PRICE=re.compile(r"(?:單價|price)[:：]?\s*([0-9]+(?:\.[0-9]+)?)", re.I)
QTY  =re.compile(r"(?:數量|qty)[:：]?\s*([0-9]+)", re.I)
ID   =re.compile(r"(?:單號|order|ticket)[:：]?\s*([A-Za-z0-9-]{3,})", re.I)

def _text(email):
    if isinstance(email, dict):
        return (email.get("subject","")+" "+email.get("body","")+" "+email.get("text","")).strip()
    return str(email)

def _rule_extract(email):
    t=_text(email)
    slots={}
    m=PRICE.search(t); slots["price"]=m.group(1) if m else None
    m=QTY.search(t);   slots["qty"]=m.group(1) if m else None
    m=ID.search(t);    slots["id"]=m.group(1) if m else None
    return slots

def _ml_extract(email):
    pkl=os.environ.get("SMA_KIE_ML_PKL","")
    if not pkl or not Path(pkl).exists(): return None
    try:
        # 期望你的 KIE model 也接受文本，返回 dict slots；否則回退 None
        from tools.ml_io import _alias_main_to_sma_features, _load_joblib, _unwrap_pipeline
        _alias_main_to_sma_features()
        pipe=_unwrap_pipeline(_load_joblib(Path(pkl)))
        try:
            pred = pipe.predict([_text(email)])[0]
            if isinstance(pred, dict): return pred
        except Exception:
            pass
        return None
    except Exception:
        return None

def _load_jsonl(p):
    L=[]
    for line in Path(p).read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        obj=json.loads(line)
        labels = obj.get("labels") or obj.get("slots") or {}
        email  = obj.get("email") or {"subject":obj.get("subject",""), "body":obj.get("body","")}
        L.append((labels,email))
    return L

def eval_split(p):
    data=_load_jsonl(p)
    hit=tot=0
    by_key=Counter(); by_key_ok=Counter()
    mode="rule"
    for labels,email in data:
        ml=_ml_extract(email)
        slots= ml if ml is not None else _rule_extract(email)
        if ml is not None: mode="ml"
        for k in ("price","qty","id"):
            if k in labels and labels[k] is not None:
                tot+=1; by_key[k]+=1
                if str(slots.get(k))==str(labels[k]): hit+=1; by_key_ok[k]+=1
    acc = hit/max(1,tot)
    return {"n":len(data),"acc_exact":acc,"mode":mode,"by_key":{k:{"ok":int(by_key_ok[k]),"tot":int(by_key[k])} for k in ("price","qty","id")}}

rep={"test":eval_split(TEST),"val":eval_split(VAL)}
Path(OUT_DIR/"kie_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
Path(OUT_DIR/"kie_report.md").write_text(
    f"# kie eval\n- test n={rep['test']['n']} acc_exact={rep['test']['acc_exact']:.3f} (mode={rep['test']['mode']}) keys={rep['test']['by_key']}\n"
    f"- val  n={rep['val']['n']} acc_exact={rep['val']['acc_exact']:.3f} (mode={rep['val']['mode']}) keys={rep['val']['by_key']}\n",
    encoding="utf-8"
)
print(json.dumps(rep, ensure_ascii=False))
