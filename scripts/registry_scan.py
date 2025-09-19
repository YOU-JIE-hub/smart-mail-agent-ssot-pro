import os,re,hashlib,json
from pathlib import Path
STATUS=Path("reports_auto/status"); STATUS.mkdir(parents=True,exist_ok=True)
def sha(p,cap=4*1024*1024):
 h=hashlib.sha256(); r=0
 with open(p,"rb") as f:
  while True:
   b=f.read(1024*1024);
   if not b: break
   r+=len(b); h.update(b);
   if r>cap: h.update(b"__TRUNCATED__"); break
 return h.hexdigest()
cands=[]
for dp, dn, fn in os.walk(Path.cwd()):
 rel=Path(dp).as_posix()
 if any(rel.startswith(x) for x in [".git",".venv","venv","node_modules","reports_auto/logs"]): continue
 for n in fn:
  p=Path(dp)/n; s=n.lower()
  if s.endswith(".pkl") or s.endswith(".safetensors") or s.endswith("model_pipeline.pkl"):
   cands.append(p)
reg={"ts":os.popen("date +%Y%m%dT%H%M%S").read().strip(),"models":[]}
for p in cands:
 t="intent" if "intent" in p.as_posix().lower() else ("spam" if "spam" in p.as_posix().lower() or "model_pipeline" in p.name else ("kie" if "safetensors" in p.suffix or "kie" in p.as_posix().lower() else "unknown"))
 reg["models"].append({"task":t,"path":p.as_posix(),"sha256":sha(p)})
(STATUS/"MODEL_REGISTRY.json").write_text(json.dumps(reg,ensure_ascii=False,indent=2),"utf-8")
print("[registry] ->", (STATUS/"MODEL_REGISTRY.json"))
