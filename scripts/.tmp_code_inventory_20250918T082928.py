import os, json, hashlib
from pathlib import Path
ROOT = Path.cwd()
TS = "20250918T082928"
out_dir = ROOT / "reports_auto" / "status"; out_dir.mkdir(parents=True, exist_ok=True)
manifest_json = out_dir / f"CODE_MANIFEST_{TS}.json"
md_path = out_dir / f"CODE_INVENTORY_{TS}.md"
tree_path = out_dir / f"PROJECT_TREE_{TS}.txt"
filelist_path = out_dir / f"FILELIST_{TS}.txt"
exc = {".git",".venv","venv","node_modules","__pycache__",".cache","dist","build","release_staging","chatpack","artifacts","artifacts_prod","artifacts_inbox","models","weights","datasets","data","reports_auto/logs"}
code_ext = {".py",".ipynb",".sh",".bash",".ps1",".bat",".cmd",".yaml",".yml",".toml",".ini",".cfg",".mk",".make",".json",".txt",".md",".rst",".sql",".env",".dockerfile",".docker",".service",".conf",".pyi",".m",".cpp",".cc",".c",".hpp",".h",".java",".kt",".ts",".tsx",".js",".jsx",".vue"}
def skip_dir(p: Path)->bool:
    rel = p.relative_to(ROOT).as_posix() if p!=ROOT else ""
    return any(rel==e or rel.startswith(e+"/") for e in exc)
def sha256_head(p: Path, cap=5*1024*1024):
    try:
        h=hashlib.sha256(); read=0
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1024*1024), b""):
                read+=len(chunk);
                if read>cap: h.update(b"__TRUNCATED__"); break
                h.update(chunk)
        return h.hexdigest()
    except Exception as e: return f"ERROR:{e}"
files=[]
for dp, dn, fn in os.walk(ROOT):
    dp=Path(dp)
    if skip_dir(dp): dn[:]=[]; continue
    for name in fn:
        p=dp/name
        if p.is_file() and (p.suffix.lower() in code_ext or p.name.lower()=="makefile"):
            rel=p.relative_to(ROOT).as_posix()
            try: sz=p.stat().st_size
            except: sz=-1
            files.append({"path":rel,"size":sz,"sha256":sha256_head(p),"mtime":int(p.stat().st_mtime)})
files.sort(key=lambda x: x["path"])
manifest={"root":str(ROOT),"ts":TS,"count":len(files),"files":files}
manifest_json.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
filelist_path.write_text("\\n".join([x["path"] for x in files]), encoding="utf-8")
def tree_lines():
    out=[]
    for dp, dn, fn in os.walk(ROOT):
        dp=Path(dp)
        if skip_dir(dp): dn[:]=[]; continue
        rel="." if dp==ROOT else dp.relative_to(ROOT).as_posix(); out.append(rel+"/")
        for name in sorted(fn):
            p=dp/name
            if p.is_file(): out.append((dp.relative_to(ROOT).as_posix() or ".") + "/" + name)
    return "\\n".join(out)
tree_path.write_text(tree_lines(), encoding="utf-8")
hdr=["# Code Inventory","","- Root: "+str(ROOT),"- TS: "+TS,"- Files: "+str(len(files)),""]
tbl=["| # | path | size(bytes) | sha256 |","|---:|:-----|-----------:|:------|"]
for i,x in enumerate(files,1): tbl.append(f"| {i} | `{x[\"path\"]}` | {x[\"size\"]} | `{x[\"sha256\"]}` |")
md_path.write_text("\\n".join(hdr+tbl)+"\\n", encoding="utf-8")
print("[OK] wrote:", manifest_json, md_path, tree_path, filelist_path)
