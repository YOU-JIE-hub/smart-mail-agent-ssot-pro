# Panic Report
- Exit code: 0
- CMD  : . .venv/bin/activate; python3 - <<'PY'
import os, json, pathlib, time
from safetensors import safe_open

root=pathlib.Path(".")
out_dir=root/"reports_auto"; out_dir.mkdir(parents=True, exist_ok=True)

d=os.environ.get("KIE_DIR","")
res={"task":"kie","dir":d}
try:
    p=pathlib.Path(d).expanduser().resolve()
    files={n:(p/n).exists() for n in ["config.json","tokenizer.json","model.safetensors"]}
    sample={}
    if files.get("model.safetensors"):
        with safe_open(str(p/"model.safetensors"), framework="pt") as f:
            ks=list(f.keys())
            for k in ks[:8]:
                sample[k]=list(f.get_tensor(k).shape)
    res.update(status="ok", files=files, sample_tensors=sample)
except Exception as e:
    res.update(status="error", error=str(e))

# 落檔＋合併回 summary.json
(out_dir/"kie_eval.json").write_text(json.dumps(res, ensure_ascii=False, indent=2),"utf-8")
sjp=root/"reports_auto/summary.json"
if sjp.exists():
    j=json.loads(sjp.read_text("utf-8"))
else:
    j={"created_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
j.setdefault("kie",{}).update({"inference":res})
sjp.write_text(json.dumps(j, ensure_ascii=False, indent=2),"utf-8")
print("[OK] KIE sanity merged into summary.json")
PY
- LOG  : reports_auto/panic_20250921T134010/run.log
- ERR  : reports_auto/panic_20250921T134010/run.err
- PY   : reports_auto/panic_20250921T134010/python_stderr.txt
- OOM  : reports_auto/panic_20250921T134010/oom.txt
- TRACE: reports_auto/panic_20250921T134010/xtrace.sh
- SYS  : reports_auto/panic_20250921T134010/system.txt

## Heuristics
