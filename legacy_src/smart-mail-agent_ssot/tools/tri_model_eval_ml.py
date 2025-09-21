from __future__ import annotations
import time, json
from pathlib import Path
from collections import Counter, defaultdict
from tools.pipeline_ml import classify_ml

ts=time.strftime("%Y%m%dT%H%M%S")
out_dir=Path(f"reports_auto/eval/{ts}"); out_dir.mkdir(parents=True, exist_ok=True)

fx=Path("fixtures/eval_set.jsonl")
if not fx.exists():
    raise SystemExit("[EVAL-ML] fixtures/eval_set.jsonl missing")

samples=[json.loads(l) for l in fx.read_text(encoding="utf-8").splitlines() if l.strip()]
y_true=[]; y_pred=[]; cm=defaultdict(Counter)
for s in samples:
    gt=s["intent"]; email=s["email"]
    pred=classify_ml(email)["intent_name"]
    y_true.append(gt); y_pred.append(pred)
    cm[gt][pred]+=1

acc=sum(1 for a,b in zip(y_true,y_pred) if a==b)/len(y_true)
summary=out_dir/"summary_ml.md"
summary.write_text(
    f"# tri-model eval (ML)\n- ts: {ts}\n- n: {len(y_true)}\n- acc: {acc:.3f}\n\n## confusion matrix\n" +
    "\n".join(f"- {gt}: {dict(cm[gt])}" for gt in cm),
    encoding="utf-8"
)
print(f"[EVAL-ML] acc={acc:.3f} -> {summary}")
