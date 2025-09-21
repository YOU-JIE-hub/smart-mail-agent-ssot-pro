from __future__ import annotations
import os, re, json, time
from pathlib import Path
from pipeline_baseline import run_pipeline

ROOT = Path(os.environ.get("ROOT") or Path.cwd())
TS = time.strftime("%Y%m%dT%H%M%S")
ACT_OUT = ROOT/f"reports_auto/actions/{TS}"
ACT_OUT.mkdir(parents=True, exist_ok=True)

# 來源：取最新 e2e_mail run 的 outbox 種子
base = ROOT/"reports_auto/e2e_mail"
runs = sorted([p for p in base.glob("*") if p.is_dir() and re.fullmatch(r"\d{8}T\d{6}", p.name)], reverse=True)
if not runs: raise SystemExit("[E2E] no timestamped run found; 先跑 one_click_patch_intent_contract_all.sh")
run = runs[0]
outbox = run/"rpa_out/email_outbox"

audit = []
for txt in outbox.glob("*.txt"):
    name = txt.stem
    body = txt.read_text(encoding="utf-8")
    subject = f"[{name}] 測試郵件"
    res = run_pipeline({"subject":subject,"body":body}, backend=os.environ.get("BACKEND","rule"))
    # 模擬 RPA：把 action 落地（示意）
    for i, act in enumerate(res["plan"]["actions"], 1):
        (ACT_OUT/f"{name}.{i}.{act['type'].replace('/','_')}.ok").write_text(json.dumps(act, ensure_ascii=False, indent=2), encoding="utf-8")
    audit.append({"seed":name, "intent_pred":res["intent"], "actions":res["plan"]["actions"]})

(Path(ACT_OUT/"audit.jsonl")).write_text("\n".join(json.dumps(a, ensure_ascii=False) for a in audit), encoding="utf-8")
print(f"[E2E] actions -> {ACT_OUT}  (seeds={len(audit)})")
