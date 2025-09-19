import os, json, sys, time, hashlib
from pathlib import Path
OUT=Path(sys.argv[1]); (OUT/"reports").mkdir(parents=True, exist_ok=True)
def safe_id(s):
 import hashlib; return hashlib.sha1((s or "").encode("utf-8")).hexdigest()[:12]
data_paths=[
 Path("data/intent_eval/dataset.cleaned.jsonl"),
 Path("data/kie_eval/gold_merged.jsonl"),
 Path("metrics/spam_metrics.json")
]
summary={"ts":int(time.time()),"counts":{}, "notes":[]}
for p in data_paths:
 if p.exists():
  if p.suffix==".jsonl": n=sum(1 for _ in p.open("r",encoding="utf-8",errors="ignore")); summary["counts"][p.as_posix()]=n
  else:
   try: import json; summary["counts"][p.as_posix()]=len(json.load(p.open("r",encoding="utf-8",errors="ignore")))
   except Exception: summary["counts"][p.as_posix()]="(ok)";
 else: summary["notes"].append(f"missing: {p}")
(OUT/"metrics.json").write_text(json.dumps({"tri_eval_light":summary},ensure_ascii=False,indent=2),"utf-8")
(OUT/"reports"/"EVAL_SUMMARY.md").write_text("# Eval(light)\\n\\n"+json.dumps(summary,ensure_ascii=False,indent=2),"utf-8")
print("[eval] light done")
