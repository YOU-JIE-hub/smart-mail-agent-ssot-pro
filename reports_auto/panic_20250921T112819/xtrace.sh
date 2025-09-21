+ CMD='python3 - <<PY
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
PY'
+ '[' -z 'python3 - <<PY
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
PY' ']'
+ echo '== SNAPSHOT 20250921T112819 =='
+ pwd
+ python3 -V
+ pip -V
+ which -a python3
+ free -h
+ df -h .
+ ulimit -a
+ env
+ grep -E 'INTENT|SPAM|PYTHONPATH'
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ set +e
+ timeout --preserve-status 3h bash -lc 'python3 - <<PY
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
PY'
++ tee -a reports_auto/panic_20250921T112819/python_stderr.txt
+ ec=1
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 1'
+ echo '- CMD  : python3 - <<PY
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
PY'
+ echo '- LOG  : reports_auto/panic_20250921T112819/run.log'
+ echo '- ERR  : reports_auto/panic_20250921T112819/run.err'
+ echo '- PY   : reports_auto/panic_20250921T112819/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250921T112819/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250921T112819/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250921T112819/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi JSONDecodeError reports_auto/panic_20250921T112819/run.err reports_auto/panic_20250921T112819/python_stderr.txt
+ grep -qi 'Permission denied' reports_auto/panic_20250921T112819/run.err reports_auto/panic_20250921T112819/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250921T112819/run.err reports_auto/panic_20250921T112819/python_stderr.txt
+ grep -qi 'only one class' reports_auto/panic_20250921T112819/run.err reports_auto/panic_20250921T112819/python_stderr.txt
+ echo -e '\n=== DIAG OUTPUTS ===\nreports_auto/panic_20250921T112819/REPORT.md\nreports_auto/panic_20250921T112819/run.log\nreports_auto/panic_20250921T112819/run.err\nreports_auto/panic_20250921T112819/python_stderr.txt\nreports_auto/panic_20250921T112819/xtrace.sh\nreports_auto/panic_20250921T112819/system.txt\nreports_auto/panic_20250921T112819/oom.txt\n'
+ exit 1
