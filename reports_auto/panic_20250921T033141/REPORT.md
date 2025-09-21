# Panic Report
- Exit code: 1
- CMD  : python3 - <<PY
import os, json, joblib, itertools, sys
from pathlib import Path

def load_any(p):
    import builtins, sys
    sys.modules.setdefault("__main__", builtins)
    setattr(sys.modules["__main__"], "rules_feat", lambda x: {})
    setattr(sys.modules["__main__"], "rules_feat_func", lambda x: {})
    obj = joblib.load(p)
    if isinstance(obj, dict):
        for k in ("pipeline","model","clf"):
            if k in obj: return obj[k]
    return obj

def head_jsonl(p, k):
    import json
    X=[]; Y=[]; n=0
    with open(p, "r", encoding="utf-8") as f:
        for i,line in enumerate(f):
            if not line.strip(): continue
            j=json.loads(line)
            if "text" in j and "label" in j:
                X.append(j["text"]); Y.append(str(j["label"])); n+=1
            if i>20000: break
    return X[:5], Y[:5], n, dict((y,Y.count(y)) for y in set(Y))

idata=os.environ["INTENT_DATA"]; sdata=os.environ["SPAM_DATA"]
intent_p=os.environ["INTENT_PKL"]; spam_p=os.environ["SPAM_PKL"]

Xi, Yi, ni, cnti = head_jsonl(idata, "intent")
Xs, Ys, ns, cnts = head_jsonl(sdata, "spam")

pi=load_any(intent_p); ps=load_any(spam_p)
res = {
 "intent": {
   "data": {"path":idata, "n":ni, "labels":cnti},
   "model": {"path":intent_p,
             "classes": getattr(getattr(pi, "steps", [[None,pi]])[-1][1], "classes_", None) or
                        getattr(pi,"classes_", None)}
 },
 "spam": {
   "data": {"path":sdata, "n":ns, "labels":cnts},
   "model": {"path":spam_p,
             "classes": getattr(getattr(ps, "steps", [[None,ps]])[-1][1], "classes_", None) or
                        getattr(ps,"classes_", None)}
 }
}
# 試著各預測三句
def p3(pipe):
    try: return list(map(str, pipe.predict(["FREE $$$ click here!!!","請問資料怎麼改？","我要投訴"])))
    except Exception as e: return f"predict_failed: {e}"
res["intent"]["smoke"]=p3(pi); res["spam"]["smoke"]=p3(ps)

out="reports_auto/verify_compat.json"
Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=2), "utf-8")
print(json.dumps(res, ensure_ascii=False, indent=2))
PY
- LOG  : reports_auto/panic_20250921T033141/run.log
- ERR  : reports_auto/panic_20250921T033141/run.err
- PY   : reports_auto/panic_20250921T033141/python_stderr.txt
- OOM  : reports_auto/panic_20250921T033141/oom.txt
- TRACE: reports_auto/panic_20250921T033141/xtrace.sh
- SYS  : reports_auto/panic_20250921T033141/system.txt

## Heuristics
