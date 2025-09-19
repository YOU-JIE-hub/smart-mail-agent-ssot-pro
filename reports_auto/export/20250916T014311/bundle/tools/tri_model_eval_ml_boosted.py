from __future__ import annotations
import time, json
from pathlib import Path
from collections import Counter, defaultdict

ts=time.strftime("%Y%m%dT%H%M%S")
out_dir=Path(f"reports_auto/eval/{ts}"); out_dir.mkdir(parents=True, exist_ok=True)
fx=Path("fixtures/eval_set.jsonl")

try:
    from tools.pipeline_ml_boosted import classify_ml_boosted as classify_b
except Exception:
    from tools.pipeline_ml_boosted import classify_boosted as classify_b

if not fx.exists():
    raise SystemExit("[EVAL-ML+] fixtures/eval_set.jsonl missing")

samples=[json.loads(l) for l in fx.read_text(encoding="utf-8").splitlines() if l.strip()]
y_true=[]; y_pred=[]; cm=defaultdict(Counter)

for s in samples:
    gt=s["intent"]; email=s["email"]
    r=classify_b(email)
    pred = r.get("intent_name") or r.get("intent")
    y_true.append(gt); y_pred.append(pred)
    cm[gt][pred]+=1

acc=sum(1 for a,b in zip(y_true,y_pred) if a==b)/len(y_true)
summary=out_dir/"summary_ml_boosted.md"
summary.write_text(
    f"# tri-model eval (ML+Boosted)\n- ts:{ts}\n- n:{len(y_true)}\n- acc:{acc:.3f}\n\n## confusion\n" +
    "\n".join(f"- {gt}: {dict(cm[gt])}" for gt in cm),
    encoding="utf-8"
)
print(f"[EVAL-ML+] n={len(y_true)} acc={acc:.3f} -> {out_dir}")

# 也產一份 machine-consumable
(out_dir/"ml_boosted_metrics.json").write_text(json.dumps({"ts":ts,"n":len(y_true),"acc":acc}, ensure_ascii=False, indent=2), encoding="utf-8")
