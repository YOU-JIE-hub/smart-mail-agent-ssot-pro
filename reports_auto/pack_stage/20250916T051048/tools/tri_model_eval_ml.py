from __future__ import annotations
import time, json
from pathlib import Path
from collections import defaultdict, Counter
from tools.pipeline_ml import classify_ml

ts=time.strftime("%Y%m%dT%H%M%S")
out=Path(f"reports_auto/eval/{ts}"); out.mkdir(parents=True, exist_ok=True)
fx=Path("fixtures/eval_set.jsonl")
if not fx.exists():
    fx.write_text("\n".join([
        json.dumps({"intent":"一般回覆","email":{"subject":"[一般回覆] 測試","body":"hello"}}),
        json.dumps({"intent":"報價","email":{"subject":"報價 單價:100 數量:2","body":""}}),
        json.dumps({"intent":"投訴","email":{"subject":"投訴","body":"客訴"}}),
        json.dumps({"intent":"技術支援","email":{"subject":"技術支援 ticket:TS-1234","body":""}}),
        json.dumps({"intent":"規則詢問","email":{"subject":"請問規則","body":"規則詢問"}}),
        json.dumps({"intent":"資料異動","email":{"subject":"資料異動 order:ORD-9","body":""}}),
    ]), encoding="utf-8")

samples=[json.loads(l) for l in fx.read_text(encoding="utf-8").splitlines() if l.strip()]
cm=defaultdict(Counter); ok=0
for s in samples:
    gt=s["intent"]; email=s["email"]
    pred=classify_ml(email)["intent_name"]
    cm[gt][pred]+=1; ok += int(pred==gt)
acc = ok/len(samples) if samples else 0.0
summary=out/"summary_ml.md"
summary.write_text(f"# tri-model eval (ML)\n- ts:{ts}\n- n:{len(samples)}\n- acc:{acc:.3f}\n\n## confusion\n" + 
                   "\n".join(f"- {gt}: {dict(cm[gt])}" for gt in cm), encoding="utf-8")
print(f"[EVAL-ML] acc={acc:.3f} -> {summary}")
