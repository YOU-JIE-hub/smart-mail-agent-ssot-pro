from __future__ import annotations
import json, time
from pathlib import Path
from tools.pipeline_baseline import load_contract, classify_rule, extract_slots_rule, plan_actions_rule
ts=time.strftime("%Y%m%dT%H%M%S")
run_dir=Path(f"reports_auto/actions/{ts}"); run_dir.mkdir(parents=True, exist_ok=True)
audit=run_dir/"audit.jsonl"
fx=Path("fixtures/eval_set.jsonl")
if not fx.exists(): raise SystemExit("[E2E] fixtures/eval_set.jsonl missing. Run tools/tri_model_eval.py once.")
contract=load_contract()
with audit.open("w", encoding="utf-8") as f:
    for line in fx.read_text(encoding="utf-8").splitlines():
        s=json.loads(line); email=s["email"]
        intent=classify_rule(email, contract); slots=extract_slots_rule(email, intent); plan=plan_actions_rule(intent, slots)
        f.write(json.dumps({"intent":intent,"slots":slots,"plan":plan,"email":email}, ensure_ascii=False)+"\n")
print(f"[E2E] wrote {audit}")
