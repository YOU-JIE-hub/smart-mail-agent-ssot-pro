from __future__ import annotations
from pathlib import Path; import hashlib, json, time
ART_DIR=Path("artifacts_prod"); OUT=ART_DIR/"manifest.json"
KEEP={"model_pipeline.pkl","ens_thresholds.json","intent_rules_calib_v11c.json","kie_runtime_config.json"}
def sha256(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1<<20), b""): h.update(b)
    return h.hexdigest()
def main():
    items=[]
    if ART_DIR.exists():
        for p in sorted(ART_DIR.rglob("*")):
            if p.is_file() and (p.name in KEEP or p.suffix in {".pkl",".json",".bin",".pt"}):
                items.append({"name":str(p.relative_to(ART_DIR)),"size":p.stat().st_size,"sha256":sha256(p)})
    OUT.write_text(json.dumps({"version":time.strftime("%Y%m%dT%H%M%S"),"artifacts":items}, indent=2, ensure_ascii=False), "utf-8")
    print(f"[OK] {OUT} written ({len(items)} items)")
if __name__=="__main__": main()
