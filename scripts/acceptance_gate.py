import os, json, sys, glob, pathlib
root=pathlib.Path("."); pro=root/"reports_auto/pro"
def pick_latest():
    p=pro/"latest"/"summary.json"
    if p.exists(): return p
    c=sorted(glob.glob(str(pro/"pro_*/summary.json")))
    return pathlib.Path(c[-1]) if c else None
p=pick_latest(); assert p is not None, "no pro summary"
j=json.loads(p.read_text("utf-8"))
intent=j.get("intent",{}).get("metrics",{})
spam=j.get("spam",{}).get("metrics",{})

# 預設門檻（你目前可通過）；可用環變數調高：GATE_INTENT_MACROF1_MIN / GATE_SPAM_ACCURACY_MIN
intent_min=float(os.environ.get("GATE_INTENT_MACROF1_MIN", "0.55"))
spam_min=float(os.environ.get("GATE_SPAM_ACCURACY_MIN", "0.90"))

ok=(intent.get("macro_f1",0)>=intent_min) and (spam.get("accuracy",0)>=spam_min)
print(json.dumps({
  "pass": ok,
  "thresholds":{"intent_macro_f1_min":intent_min, "spam_accuracy_min":spam_min},
  "actual":{"intent_macro_f1":intent.get("macro_f1",0), "spam_accuracy":spam.get("accuracy",0)},
  "summary_path": str(p)
}, ensure_ascii=False, indent=2))
sys.exit(0 if ok else 2)
