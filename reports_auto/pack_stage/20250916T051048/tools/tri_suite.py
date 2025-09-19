from __future__ import annotations
import json, time, inspect
from pathlib import Path
from collections import defaultdict

FIXTURES = Path("fixtures/eval_set.jsonl")
OUTROOT  = Path("reports_auto/eval")

# ─── 通用：把不同後端的回傳統一成 (intent:str, conf:float) ───
def _norm_pair(r):
    if isinstance(r, dict):
        intent = r.get("intent") or r.get("label") or r.get("pred") or ""
        conf   = r.get("confidence") or r.get("conf") or r.get("score") or 1.0
        try: conf = float(conf)
        except Exception: conf = 1.0
        return (str(intent), conf)
    if isinstance(r, (list, tuple)):
        if len(r) >= 2:
            try: return (str(r[0]), float(r[1]))
            except Exception: return (str(r[0]), 1.0)
        if len(r) == 1: return (str(r[0]), 1.0)
    if isinstance(r, str): return (r, 1.0)
    return ("", 0.0)

# ─── Baseline 規則：簽名可能需要 contract，也可能不需要 ───
def _classify_rule(email: dict):
    from tools import pipeline_baseline as base
    cls = getattr(base, "classify_rule", None) or getattr(base, "classify", None)
    if cls is None:
        raise ImportError("pipeline_baseline: classify_rule/classify not found")
    sig = None
    try: sig = inspect.signature(cls)
    except Exception: sig = None
    if sig and "contract" in sig.parameters:
        load_contract = getattr(base, "load_contract", None)
        contract = load_contract() if callable(load_contract) else None
        r = cls(email, contract)
    else:
        r = cls(email)
    return _norm_pair(r)

# ─── ML：允許直接回傳中文類別或英文類別；這裡只做 normalize ───
def _classify_ml(email: dict):
    from tools.pipeline_ml import classify_ml
    return _norm_pair(classify_ml(email))

# ─── Boosted：允許 tuple/dict ───
def _classify_boosted(email: dict):
    # 支援你現有的 classify_boosted / classify_ml_boosted 任何一個
    try:
        from tools.pipeline_ml_boosted import classify_boosted as f
    except Exception:
        from tools.pipeline_ml_boosted import classify_ml_boosted as f
    return _norm_pair(f(email))

def _load_samples():
    rows=[]
    with open(FIXTURES, "r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            rows.append(json.loads(line))
    return rows

def _eval_backend(rows, name: str, caller):
    y_true=[]; y_pred=[]
    for r in rows:
        gold = r.get("intent","")
        pred, _ = caller(r.get("email") or {})
        y_true.append(gold); y_pred.append(pred or "")
    # confusion: {gold: {pred: count}}
    conf=defaultdict(lambda: defaultdict(int))
    correct=0
    for g,p in zip(y_true,y_pred):
        conf[g][p]+=1
        if g==p: correct+=1
    return {
        "n": len(y_true),
        "acc": (correct/len(y_true)) if y_true else 0.0,
        "confusion": {g: dict(conf[g]) for g in conf}
    }

def main():
    rows=_load_samples()
    ts=time.strftime("%Y%m%dT%H%M%S")
    outdir=(OUTROOT/ts); outdir.mkdir(parents=True, exist_ok=True)

    result={}
    result["ts"]=ts
    result["intent_rule"]    = _eval_backend(rows, "rule",     _classify_rule)
    result["intent_ml"]      = _eval_backend(rows, "ml",       _classify_ml)
    result["intent_boosted"] = _eval_backend(rows, "boosted",  _classify_boosted)

    (outdir/"tri_suite.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[TRI] wrote {outdir/'tri_suite.json'}")

if __name__=="__main__":
    main()
