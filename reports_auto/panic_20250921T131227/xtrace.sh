+ CMD='. .venv/bin/activate; python3 - <<PY
import os, json, pathlib, hashlib, time, joblib
def sha(p): 
    b=pathlib.Path(p).read_bytes(); 
    import hashlib as h; 
    return h.sha256(b).hexdigest()
def dump_pkl(env):
    p=os.environ.get(env); 
    if not p: return
    P=pathlib.Path(p).expanduser().resolve()
    d={"path":str(P),"exists":P.exists(),"generated_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
    if P.exists():
        d.update(size_bytes=P.stat().st_size, sha256=sha(P))
        try:
            m=joblib.load(P); d["classes_"]=list(getattr(m,"classes_",[])); d["sklearn_pipeline"]=type(m).__name__
        except Exception as e: d["load_error"]=str(e)
    (P.parent/"PROVENANCE.json").write_text(json.dumps(d, ensure_ascii=False, indent=2),"utf-8")
def dump_kie():
    d=os.environ.get("KIE_DIR"); 
    if not d: return
    D=pathlib.Path(d).expanduser().resolve()
    files=["config.json","tokenizer.json","model.safetensors"]
    mp={"dir":str(D),"generated_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
    mp["files"]={f: (D/f).exists() for f in files}
    mp["files_sha256"]={f: (sha(D/f) if (D/f).exists() else None) for f in files}
    (D/"PROVENANCE.json").write_text(json.dumps(mp, ensure_ascii=False, indent=2),"utf-8")
dump_pkl("INTENT_PKL"); dump_pkl("SPAM_PKL"); dump_kie(); print("[OK] provenance updated")
PY'
+ '[' -z '. .venv/bin/activate; python3 - <<PY
import os, json, pathlib, hashlib, time, joblib
def sha(p): 
    b=pathlib.Path(p).read_bytes(); 
    import hashlib as h; 
    return h.sha256(b).hexdigest()
def dump_pkl(env):
    p=os.environ.get(env); 
    if not p: return
    P=pathlib.Path(p).expanduser().resolve()
    d={"path":str(P),"exists":P.exists(),"generated_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
    if P.exists():
        d.update(size_bytes=P.stat().st_size, sha256=sha(P))
        try:
            m=joblib.load(P); d["classes_"]=list(getattr(m,"classes_",[])); d["sklearn_pipeline"]=type(m).__name__
        except Exception as e: d["load_error"]=str(e)
    (P.parent/"PROVENANCE.json").write_text(json.dumps(d, ensure_ascii=False, indent=2),"utf-8")
def dump_kie():
    d=os.environ.get("KIE_DIR"); 
    if not d: return
    D=pathlib.Path(d).expanduser().resolve()
    files=["config.json","tokenizer.json","model.safetensors"]
    mp={"dir":str(D),"generated_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
    mp["files"]={f: (D/f).exists() for f in files}
    mp["files_sha256"]={f: (sha(D/f) if (D/f).exists() else None) for f in files}
    (D/"PROVENANCE.json").write_text(json.dumps(mp, ensure_ascii=False, indent=2),"utf-8")
dump_pkl("INTENT_PKL"); dump_pkl("SPAM_PKL"); dump_kie(); print("[OK] provenance updated")
PY' ']'
+ echo '== SNAPSHOT 20250921T131227 =='
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
+ timeout --preserve-status 3h bash -lc '. .venv/bin/activate; python3 - <<PY
import os, json, pathlib, hashlib, time, joblib
def sha(p): 
    b=pathlib.Path(p).read_bytes(); 
    import hashlib as h; 
    return h.sha256(b).hexdigest()
def dump_pkl(env):
    p=os.environ.get(env); 
    if not p: return
    P=pathlib.Path(p).expanduser().resolve()
    d={"path":str(P),"exists":P.exists(),"generated_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
    if P.exists():
        d.update(size_bytes=P.stat().st_size, sha256=sha(P))
        try:
            m=joblib.load(P); d["classes_"]=list(getattr(m,"classes_",[])); d["sklearn_pipeline"]=type(m).__name__
        except Exception as e: d["load_error"]=str(e)
    (P.parent/"PROVENANCE.json").write_text(json.dumps(d, ensure_ascii=False, indent=2),"utf-8")
def dump_kie():
    d=os.environ.get("KIE_DIR"); 
    if not d: return
    D=pathlib.Path(d).expanduser().resolve()
    files=["config.json","tokenizer.json","model.safetensors"]
    mp={"dir":str(D),"generated_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
    mp["files"]={f: (D/f).exists() for f in files}
    mp["files_sha256"]={f: (sha(D/f) if (D/f).exists() else None) for f in files}
    (D/"PROVENANCE.json").write_text(json.dumps(mp, ensure_ascii=False, indent=2),"utf-8")
dump_pkl("INTENT_PKL"); dump_pkl("SPAM_PKL"); dump_kie(); print("[OK] provenance updated")
PY'
++ tee -a reports_auto/panic_20250921T131227/python_stderr.txt
+ ec=1
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 1'
+ echo '- CMD  : . .venv/bin/activate; python3 - <<PY
import os, json, pathlib, hashlib, time, joblib
def sha(p): 
    b=pathlib.Path(p).read_bytes(); 
    import hashlib as h; 
    return h.sha256(b).hexdigest()
def dump_pkl(env):
    p=os.environ.get(env); 
    if not p: return
    P=pathlib.Path(p).expanduser().resolve()
    d={"path":str(P),"exists":P.exists(),"generated_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
    if P.exists():
        d.update(size_bytes=P.stat().st_size, sha256=sha(P))
        try:
            m=joblib.load(P); d["classes_"]=list(getattr(m,"classes_",[])); d["sklearn_pipeline"]=type(m).__name__
        except Exception as e: d["load_error"]=str(e)
    (P.parent/"PROVENANCE.json").write_text(json.dumps(d, ensure_ascii=False, indent=2),"utf-8")
def dump_kie():
    d=os.environ.get("KIE_DIR"); 
    if not d: return
    D=pathlib.Path(d).expanduser().resolve()
    files=["config.json","tokenizer.json","model.safetensors"]
    mp={"dir":str(D),"generated_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
    mp["files"]={f: (D/f).exists() for f in files}
    mp["files_sha256"]={f: (sha(D/f) if (D/f).exists() else None) for f in files}
    (D/"PROVENANCE.json").write_text(json.dumps(mp, ensure_ascii=False, indent=2),"utf-8")
dump_pkl("INTENT_PKL"); dump_pkl("SPAM_PKL"); dump_kie(); print("[OK] provenance updated")
PY'
+ echo '- LOG  : reports_auto/panic_20250921T131227/run.log'
+ echo '- ERR  : reports_auto/panic_20250921T131227/run.err'
+ echo '- PY   : reports_auto/panic_20250921T131227/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250921T131227/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250921T131227/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250921T131227/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi JSONDecodeError reports_auto/panic_20250921T131227/run.err reports_auto/panic_20250921T131227/python_stderr.txt
+ grep -qi 'Permission denied' reports_auto/panic_20250921T131227/run.err reports_auto/panic_20250921T131227/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250921T131227/run.err reports_auto/panic_20250921T131227/python_stderr.txt
+ grep -qi 'only one class' reports_auto/panic_20250921T131227/run.err reports_auto/panic_20250921T131227/python_stderr.txt
+ echo -e '\n=== DIAG OUTPUTS ===\nreports_auto/panic_20250921T131227/REPORT.md\nreports_auto/panic_20250921T131227/run.log\nreports_auto/panic_20250921T131227/run.err\nreports_auto/panic_20250921T131227/python_stderr.txt\nreports_auto/panic_20250921T131227/xtrace.sh\nreports_auto/panic_20250921T131227/system.txt\nreports_auto/panic_20250921T131227/oom.txt\n'
+ exit 1
