from __future__ import annotations
import time, json
from pathlib import Path
from tools.pipeline_ml import classify_ml

ts=time.strftime("%Y%m%dT%H%M%S")
run_dir=Path(f"reports_auto/actions/{ts}"); run_dir.mkdir(parents=True, exist_ok=True)
audit=run_dir/"audit_ml.jsonl"

fx=Path("fixtures/eval_set.jsonl")
if not fx.exists():
    raise SystemExit("[E2E-ML] fixtures/eval_set.jsonl missing")

with audit.open("w", encoding="utf-8") as f:
    for line in fx.read_text(encoding="utf-8").splitlines():
        s=json.loads(line); email=s["email"]
        pred=classify_ml(email)
        # 這裡仍可串接你現有的 RPA 規劃/執行；先留審計
        f.write(json.dumps({"email":email, "ml":pred}, ensure_ascii=False)+"\n")

print(f"[E2E-ML] wrote {audit}")
