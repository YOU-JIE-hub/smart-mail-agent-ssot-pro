from __future__ import annotations
import time, json
from pathlib import Path
from tools.pipeline_ml_boosted import classify_ml_boosted

ts=time.strftime("%Y%m%dT%H%M%S")
run_dir=Path(f"reports_auto/actions/{ts}"); run_dir.mkdir(parents=True, exist_ok=True)
audit=run_dir/"audit_ml_boosted.jsonl"

fx=Path("fixtures/eval_set.jsonl")
if not fx.exists():
    raise SystemExit("[E2E-ML+] fixtures/eval_set.jsonl missing")

with audit.open("w", encoding="utf-8") as f:
    for line in fx.read_text(encoding="utf-8").splitlines():
        s=json.loads(line); email=s["email"]
        pred=classify_ml_boosted(email)
        f.write(json.dumps({"email":email, "ml_boosted":pred}, ensure_ascii=False)+"\n")

print(f"[E2E-ML+] wrote {audit}")
