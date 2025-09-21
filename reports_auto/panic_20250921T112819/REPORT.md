# Panic Report
- Exit code: 1
- CMD  : python3 - <<PY
import os, json, time, hashlib, pathlib, joblib

def provenance_of(pkl_path):
p=pathlib.Path(pkl_path).expanduser().resolve()
d={"path": str(p), "exists": p.exists(), "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
if not p.exists(): return d
b=p.read_bytes()
d.update({
"size_bytes": len(b),
"sha256": hashlib.sha256(b).hexdigest(),
})
try:
m=joblib.load(p)
d["classes_"]=list(getattr(m,"classes_", []))
d["sklearn_pipeline"]=type(m).name
except Exception as e:
d["load_error"]=str(e)
# 就地寫入
out=p.parent/"PROVENANCE.json"
out.write_text(json.dumps(d, ensure_ascii=False, indent=2), "utf-8")
return d

intent=os.environ.get("INTENT_PKL"); spam=os.environ.get("SPAM_PKL")
prov={}
if intent: prov["intent"]=provenance_of(intent)
if spam: prov["spam"]=provenance_of(spam)
print(json.dumps(prov, ensure_ascii=False, indent=2))
PY
- LOG  : reports_auto/panic_20250921T112819/run.log
- ERR  : reports_auto/panic_20250921T112819/run.err
- PY   : reports_auto/panic_20250921T112819/python_stderr.txt
- OOM  : reports_auto/panic_20250921T112819/oom.txt
- TRACE: reports_auto/panic_20250921T112819/xtrace.sh
- SYS  : reports_auto/panic_20250921T112819/system.txt

## Heuristics
