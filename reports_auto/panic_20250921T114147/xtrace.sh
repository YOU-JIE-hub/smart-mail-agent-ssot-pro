+ CMD='. .venv/bin/activate; python3 - <<'\''PY'\''
import os, json, time, hashlib, pathlib, joblib
def provenance_of(pkl_path):
    p=pathlib.Path(pkl_path).expanduser().resolve()
    d={"path": str(p), "exists": p.exists(), "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if not p.exists(): return d
    b=p.read_bytes()
    d.update({"size_bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()})
    try:
        m=joblib.load(p)
        d["classes_"]=list(getattr(m,"classes_", []))
        d["sklearn_pipeline"]=type(m).__name__
    except Exception as e:
        d["load_error"]=str(e)
    (p.parent/"PROVENANCE.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), "utf-8")
    return d

prov={}
if os.environ.get("INTENT_PKL"): prov["intent"]=provenance_of(os.environ["INTENT_PKL"])
if os.environ.get("SPAM_PKL"):   prov["spam"]=provenance_of(os.environ["SPAM_PKL"])
print(json.dumps(prov, ensure_ascii=False, indent=2))
PY'
+ '[' -z '. .venv/bin/activate; python3 - <<'\''PY'\''
import os, json, time, hashlib, pathlib, joblib
def provenance_of(pkl_path):
    p=pathlib.Path(pkl_path).expanduser().resolve()
    d={"path": str(p), "exists": p.exists(), "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if not p.exists(): return d
    b=p.read_bytes()
    d.update({"size_bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()})
    try:
        m=joblib.load(p)
        d["classes_"]=list(getattr(m,"classes_", []))
        d["sklearn_pipeline"]=type(m).__name__
    except Exception as e:
        d["load_error"]=str(e)
    (p.parent/"PROVENANCE.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), "utf-8")
    return d

prov={}
if os.environ.get("INTENT_PKL"): prov["intent"]=provenance_of(os.environ["INTENT_PKL"])
if os.environ.get("SPAM_PKL"):   prov["spam"]=provenance_of(os.environ["SPAM_PKL"])
print(json.dumps(prov, ensure_ascii=False, indent=2))
PY' ']'
+ echo '== SNAPSHOT 20250921T114147 =='
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
+ timeout --preserve-status 3h bash -lc '. .venv/bin/activate; python3 - <<'\''PY'\''
import os, json, time, hashlib, pathlib, joblib
def provenance_of(pkl_path):
    p=pathlib.Path(pkl_path).expanduser().resolve()
    d={"path": str(p), "exists": p.exists(), "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if not p.exists(): return d
    b=p.read_bytes()
    d.update({"size_bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()})
    try:
        m=joblib.load(p)
        d["classes_"]=list(getattr(m,"classes_", []))
        d["sklearn_pipeline"]=type(m).__name__
    except Exception as e:
        d["load_error"]=str(e)
    (p.parent/"PROVENANCE.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), "utf-8")
    return d

prov={}
if os.environ.get("INTENT_PKL"): prov["intent"]=provenance_of(os.environ["INTENT_PKL"])
if os.environ.get("SPAM_PKL"):   prov["spam"]=provenance_of(os.environ["SPAM_PKL"])
print(json.dumps(prov, ensure_ascii=False, indent=2))
PY'
++ tee -a reports_auto/panic_20250921T114147/python_stderr.txt
+ ec=1
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 1'
+ echo '- CMD  : . .venv/bin/activate; python3 - <<'\''PY'\''
import os, json, time, hashlib, pathlib, joblib
def provenance_of(pkl_path):
    p=pathlib.Path(pkl_path).expanduser().resolve()
    d={"path": str(p), "exists": p.exists(), "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if not p.exists(): return d
    b=p.read_bytes()
    d.update({"size_bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()})
    try:
        m=joblib.load(p)
        d["classes_"]=list(getattr(m,"classes_", []))
        d["sklearn_pipeline"]=type(m).__name__
    except Exception as e:
        d["load_error"]=str(e)
    (p.parent/"PROVENANCE.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), "utf-8")
    return d

prov={}
if os.environ.get("INTENT_PKL"): prov["intent"]=provenance_of(os.environ["INTENT_PKL"])
if os.environ.get("SPAM_PKL"):   prov["spam"]=provenance_of(os.environ["SPAM_PKL"])
print(json.dumps(prov, ensure_ascii=False, indent=2))
PY'
+ echo '- LOG  : reports_auto/panic_20250921T114147/run.log'
+ echo '- ERR  : reports_auto/panic_20250921T114147/run.err'
+ echo '- PY   : reports_auto/panic_20250921T114147/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250921T114147/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250921T114147/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250921T114147/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi JSONDecodeError reports_auto/panic_20250921T114147/run.err reports_auto/panic_20250921T114147/python_stderr.txt
+ grep -qi 'Permission denied' reports_auto/panic_20250921T114147/run.err reports_auto/panic_20250921T114147/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250921T114147/run.err reports_auto/panic_20250921T114147/python_stderr.txt
+ grep -qi 'only one class' reports_auto/panic_20250921T114147/run.err reports_auto/panic_20250921T114147/python_stderr.txt
+ echo -e '\n=== DIAG OUTPUTS ===\nreports_auto/panic_20250921T114147/REPORT.md\nreports_auto/panic_20250921T114147/run.log\nreports_auto/panic_20250921T114147/run.err\nreports_auto/panic_20250921T114147/python_stderr.txt\nreports_auto/panic_20250921T114147/xtrace.sh\nreports_auto/panic_20250921T114147/system.txt\nreports_auto/panic_20250921T114147/oom.txt\n'
+ exit 1
