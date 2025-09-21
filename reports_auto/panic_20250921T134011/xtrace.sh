+ CMD='. .venv/bin/activate; python3 - <<'\''PY'\''
import os, json, pathlib, time, hashlib, joblib
def sha256_of(path):
    p=pathlib.Path(path)
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()

root=pathlib.Path("."); out= {}
for env in ("INTENT_PKL","SPAM_PKL"):
    p=os.environ.get(env)
    if not p: continue
    P=pathlib.Path(p).expanduser().resolve()
    d={"path":str(P), "exists":P.exists(), "generated_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
    if P.exists():
        d.update(size_bytes=P.stat().st_size, sha256=sha256_of(P))
        try:
            m=joblib.load(P)
            import numpy as np
            classes=list(getattr(m,"classes_",[]))
            d["classes_"]=[(str(c) if not isinstance(c,(int,float)) else c) for c in classes]
            d["sklearn_pipeline"]=type(m).__name__
        except Exception as e:
            d["load_error"]=str(e)
        (P.parent/"PROVENANCE.json").write_text(json.dumps(d, ensure_ascii=False, indent=2),"utf-8")
    out[env.lower()] = d

# KIE 目錄檢核 + 檔案 SHA
kd=os.environ.get("KIE_DIR","")
if kd:
    D=pathlib.Path(kd).expanduser().resolve()
    files=["config.json","tokenizer.json","model.safetensors"]
    mp={"dir":str(D), "generated_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
    mp["files"]={f:(D/f).exists() for f in files}
    mp["files_sha256"]={f:(sha256_of(D/f) if (D/f).exists() else None) for f in files}
    (D/"PROVENANCE.json").write_text(json.dumps(mp, ensure_ascii=False, indent=2),"utf-8")
    out["kie"]=mp

# 合併回 summary.json
sjp=root/"reports_auto/summary.json"
j=json.loads(sjp.read_text("utf-8")) if sjp.exists() else {"created_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
j["provenance"]=j.get("provenance",{})
# 對齊鍵名
if "INTENT_PKL".lower() in out: j["provenance"]["intent"]=out["intent_pkl"]
if "SPAM_PKL".lower()   in out: j["provenance"]["spam"]=out["spam_pkl"]
if "kie"                in out: j["provenance"]["kie"]=out["kie"]
sjp.write_text(json.dumps(j, ensure_ascii=False, indent=2),"utf-8")
print("[OK] provenance merged:", list(j.get("provenance",{}).keys()))
PY'
+ '[' -z '. .venv/bin/activate; python3 - <<'\''PY'\''
import os, json, pathlib, time, hashlib, joblib
def sha256_of(path):
    p=pathlib.Path(path)
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()

root=pathlib.Path("."); out= {}
for env in ("INTENT_PKL","SPAM_PKL"):
    p=os.environ.get(env)
    if not p: continue
    P=pathlib.Path(p).expanduser().resolve()
    d={"path":str(P), "exists":P.exists(), "generated_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
    if P.exists():
        d.update(size_bytes=P.stat().st_size, sha256=sha256_of(P))
        try:
            m=joblib.load(P)
            import numpy as np
            classes=list(getattr(m,"classes_",[]))
            d["classes_"]=[(str(c) if not isinstance(c,(int,float)) else c) for c in classes]
            d["sklearn_pipeline"]=type(m).__name__
        except Exception as e:
            d["load_error"]=str(e)
        (P.parent/"PROVENANCE.json").write_text(json.dumps(d, ensure_ascii=False, indent=2),"utf-8")
    out[env.lower()] = d

# KIE 目錄檢核 + 檔案 SHA
kd=os.environ.get("KIE_DIR","")
if kd:
    D=pathlib.Path(kd).expanduser().resolve()
    files=["config.json","tokenizer.json","model.safetensors"]
    mp={"dir":str(D), "generated_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
    mp["files"]={f:(D/f).exists() for f in files}
    mp["files_sha256"]={f:(sha256_of(D/f) if (D/f).exists() else None) for f in files}
    (D/"PROVENANCE.json").write_text(json.dumps(mp, ensure_ascii=False, indent=2),"utf-8")
    out["kie"]=mp

# 合併回 summary.json
sjp=root/"reports_auto/summary.json"
j=json.loads(sjp.read_text("utf-8")) if sjp.exists() else {"created_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
j["provenance"]=j.get("provenance",{})
# 對齊鍵名
if "INTENT_PKL".lower() in out: j["provenance"]["intent"]=out["intent_pkl"]
if "SPAM_PKL".lower()   in out: j["provenance"]["spam"]=out["spam_pkl"]
if "kie"                in out: j["provenance"]["kie"]=out["kie"]
sjp.write_text(json.dumps(j, ensure_ascii=False, indent=2),"utf-8")
print("[OK] provenance merged:", list(j.get("provenance",{}).keys()))
PY' ']'
+ echo '== SNAPSHOT 20250921T134011 =='
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
import os, json, pathlib, time, hashlib, joblib
def sha256_of(path):
    p=pathlib.Path(path)
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()

root=pathlib.Path("."); out= {}
for env in ("INTENT_PKL","SPAM_PKL"):
    p=os.environ.get(env)
    if not p: continue
    P=pathlib.Path(p).expanduser().resolve()
    d={"path":str(P), "exists":P.exists(), "generated_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
    if P.exists():
        d.update(size_bytes=P.stat().st_size, sha256=sha256_of(P))
        try:
            m=joblib.load(P)
            import numpy as np
            classes=list(getattr(m,"classes_",[]))
            d["classes_"]=[(str(c) if not isinstance(c,(int,float)) else c) for c in classes]
            d["sklearn_pipeline"]=type(m).__name__
        except Exception as e:
            d["load_error"]=str(e)
        (P.parent/"PROVENANCE.json").write_text(json.dumps(d, ensure_ascii=False, indent=2),"utf-8")
    out[env.lower()] = d

# KIE 目錄檢核 + 檔案 SHA
kd=os.environ.get("KIE_DIR","")
if kd:
    D=pathlib.Path(kd).expanduser().resolve()
    files=["config.json","tokenizer.json","model.safetensors"]
    mp={"dir":str(D), "generated_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
    mp["files"]={f:(D/f).exists() for f in files}
    mp["files_sha256"]={f:(sha256_of(D/f) if (D/f).exists() else None) for f in files}
    (D/"PROVENANCE.json").write_text(json.dumps(mp, ensure_ascii=False, indent=2),"utf-8")
    out["kie"]=mp

# 合併回 summary.json
sjp=root/"reports_auto/summary.json"
j=json.loads(sjp.read_text("utf-8")) if sjp.exists() else {"created_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
j["provenance"]=j.get("provenance",{})
# 對齊鍵名
if "INTENT_PKL".lower() in out: j["provenance"]["intent"]=out["intent_pkl"]
if "SPAM_PKL".lower()   in out: j["provenance"]["spam"]=out["spam_pkl"]
if "kie"                in out: j["provenance"]["kie"]=out["kie"]
sjp.write_text(json.dumps(j, ensure_ascii=False, indent=2),"utf-8")
print("[OK] provenance merged:", list(j.get("provenance",{}).keys()))
PY'
++ tee -a reports_auto/panic_20250921T134011/python_stderr.txt
+ ec=0
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 0'
+ echo '- CMD  : . .venv/bin/activate; python3 - <<'\''PY'\''
import os, json, pathlib, time, hashlib, joblib
def sha256_of(path):
    p=pathlib.Path(path)
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()

root=pathlib.Path("."); out= {}
for env in ("INTENT_PKL","SPAM_PKL"):
    p=os.environ.get(env)
    if not p: continue
    P=pathlib.Path(p).expanduser().resolve()
    d={"path":str(P), "exists":P.exists(), "generated_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
    if P.exists():
        d.update(size_bytes=P.stat().st_size, sha256=sha256_of(P))
        try:
            m=joblib.load(P)
            import numpy as np
            classes=list(getattr(m,"classes_",[]))
            d["classes_"]=[(str(c) if not isinstance(c,(int,float)) else c) for c in classes]
            d["sklearn_pipeline"]=type(m).__name__
        except Exception as e:
            d["load_error"]=str(e)
        (P.parent/"PROVENANCE.json").write_text(json.dumps(d, ensure_ascii=False, indent=2),"utf-8")
    out[env.lower()] = d

# KIE 目錄檢核 + 檔案 SHA
kd=os.environ.get("KIE_DIR","")
if kd:
    D=pathlib.Path(kd).expanduser().resolve()
    files=["config.json","tokenizer.json","model.safetensors"]
    mp={"dir":str(D), "generated_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
    mp["files"]={f:(D/f).exists() for f in files}
    mp["files_sha256"]={f:(sha256_of(D/f) if (D/f).exists() else None) for f in files}
    (D/"PROVENANCE.json").write_text(json.dumps(mp, ensure_ascii=False, indent=2),"utf-8")
    out["kie"]=mp

# 合併回 summary.json
sjp=root/"reports_auto/summary.json"
j=json.loads(sjp.read_text("utf-8")) if sjp.exists() else {"created_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
j["provenance"]=j.get("provenance",{})
# 對齊鍵名
if "INTENT_PKL".lower() in out: j["provenance"]["intent"]=out["intent_pkl"]
if "SPAM_PKL".lower()   in out: j["provenance"]["spam"]=out["spam_pkl"]
if "kie"                in out: j["provenance"]["kie"]=out["kie"]
sjp.write_text(json.dumps(j, ensure_ascii=False, indent=2),"utf-8")
print("[OK] provenance merged:", list(j.get("provenance",{}).keys()))
PY'
+ echo '- LOG  : reports_auto/panic_20250921T134011/run.log'
+ echo '- ERR  : reports_auto/panic_20250921T134011/run.err'
+ echo '- PY   : reports_auto/panic_20250921T134011/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250921T134011/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250921T134011/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250921T134011/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi JSONDecodeError reports_auto/panic_20250921T134011/run.err reports_auto/panic_20250921T134011/python_stderr.txt
+ grep -qi 'Permission denied' reports_auto/panic_20250921T134011/run.err reports_auto/panic_20250921T134011/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250921T134011/run.err reports_auto/panic_20250921T134011/python_stderr.txt
+ grep -qi 'only one class' reports_auto/panic_20250921T134011/run.err reports_auto/panic_20250921T134011/python_stderr.txt
+ echo -e '\n=== DIAG OUTPUTS ===\nreports_auto/panic_20250921T134011/REPORT.md\nreports_auto/panic_20250921T134011/run.log\nreports_auto/panic_20250921T134011/run.err\nreports_auto/panic_20250921T134011/python_stderr.txt\nreports_auto/panic_20250921T134011/xtrace.sh\nreports_auto/panic_20250921T134011/system.txt\nreports_auto/panic_20250921T134011/oom.txt\n'
+ exit 0
