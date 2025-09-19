from __future__ import annotations
import json, time
from pathlib import Path
from collections import Counter, defaultdict
from tools.pipeline_baseline import load_contract, classify_rule
ts=time.strftime("%Y%m%dT%H%M%S")
out_dir=Path(f"reports_auto/eval/{ts}"); out_dir.mkdir(parents=True, exist_ok=True)
contract=load_contract()
fx=Path("fixtures/eval_set.jsonl")
if not fx.exists():
    fx.parent.mkdir(parents=True, exist_ok=True)
    fx.write_text("\n".join([
        json.dumps({"intent":"一般回覆","email":{"subject":"[一般回覆] test","body":"hello"}}),
        json.dumps({"intent":"報價","email":{"subject":"報價 單價:100 數量:2","body":""}}),
        json.dumps({"intent":"投訴","email":{"subject":"投訴","body":"客訴"}}),
        json.dumps({"intent":"技術支援","email":{"subject":"技術支援 ticket:TS-1234","body":""}}),
        json.dumps({"intent":"規則詢問","email":{"subject":"請問規則","body":"規則詢問"}}),
        json.dumps({"intent":"資料異動","email":{"subject":"請協助資料異動 order:ORD-9","body":""}}),
    ]), encoding="utf-8")
samples=[json.loads(l) for l in fx.read_text(encoding="utf-8").splitlines() if l.strip()]
y_true=[]; y_pred=[]; by_gt=defaultdict(Counter)
for s in samples:
    gt=s["intent"]; pred=classify_rule(s["email"], contract)
    y_true.append(gt); y_pred.append(pred); by_gt[gt][pred]+=1
acc=sum(1 for a,b in zip(y_true,y_pred) if a==b)/len(y_true)
summary=Path(out_dir/"summary.md")
summary.write_text(f"# tri-model eval (rule)\n- ts: {ts}\n- n: {len(y_true)}\n- acc: {acc:.3f}\n\n## confusion (gt->pred)\n"+"\n".join(f"- {gt}: {dict(by_gt[gt])}" for gt in by_gt), encoding="utf-8")
print(f"[EVAL] acc={acc:.3f} -> {summary}")
