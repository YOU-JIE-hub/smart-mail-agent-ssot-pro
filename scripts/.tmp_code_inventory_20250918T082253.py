import os, sys, json, hashlib, time
from pathlib import Path
ROOT = Path.cwd()
TS = "20250918T082253"
out_dir = ROOT / "reports_auto" / "status"
out_dir.mkdir(parents=True, exist_ok=True)
manifest_json = out_dir / f"CODE_MANIFEST_{TS}.json"
md_path = out_dir / f"CODE_INVENTORY_{TS}.md"
tree_path = out_dir / f"PROJECT_TREE_{TS}.txt"
filelist_path = out_dir / f"FILELIST_{TS}.txt"
excludes = {".git",".venv","venv","node_modules","__pycache__",".cache","dist","build","release_staging","chatpack","artifacts","artifacts_prod","artifacts_inbox","models","weights","datasets","data","reports_auto/logs"}
code_ext = {".py",".ipynb",".sh",".bash",".ps1",".bat",".cmd",".yaml",".yml",".toml",".ini",".cfg",".mk",".make",".json",".txt",".md",".rst",".sql",".env",".dockerfile",".docker",".service",".conf",".pyi",".m",".cpp",".cc",".c",".hpp",".h",".java",".kt",".ts",".tsx",".js",".jsx",".vue"}
def should_skip_dir(p: Path)->bool:
    rel = p.relative_to(ROOT).as_posix() if p != ROOT else ""
    for ex in excludes:
        if rel == ex or rel.startswith(ex + "/"): return True
    return False
def sha256_head(p: Path, max_bytes=5*1024*1024):
    try:
        h = hashlib.sha256(); n=0
        with p.open("rb") as f:
            while True:
                b = f.read(1024*1024); n+=len(b);
                if not b: break
                if n > max_bytes: h.update(b"__TRUNCATED__"); break
                h.update(b)
        return h.hexdigest()
    except Exception as e:
        return f"ERROR:{e}"
files=[]
for dp, dn, fn in os.walk(ROOT):
    dp = Path(dp)
    if should_skip_dir(dp):
        dn[:] = []
        continue
    for name in fn:
        p = dp / name
        if p.is_file() and (p.suffix.lower() in code_ext or p.name.lower()=="makefile"):
            rel = p.relative_to(ROOT).as_posix()
            try: sz = p.stat().st_size
            except: sz = -1
            files.append({"path":rel,"size":sz,"sha256":sha256_head(p),"mtime":int(p.stat().st_mtime)})
files.sort(key=lambda x: x["path"])
with manifest_json.open("w", encoding="utf-8") as f: json.dump({"root":str(ROOT),"ts":TS,"count":len(files),"files":files}, f, ensure_ascii=False, indent=2)
with filelist_path.open("w", encoding="utf-8") as f: f.write("\\n".join([x["path"] for x in files]))
# 專案樹（僅顯示未排除目錄）
def tree_lines():
    lines=[]
    for dp, dn, fn in os.walk(ROOT):
        dp = Path(dp)
        if should_skip_dir(dp): dn[:] = []; continue
        rel = "." if dp==ROOT else dp.relative_to(ROOT).as_posix()
        lines.append(rel + "/")
        for name in sorted(fn):
            p = dp / name
            if p.is_file(): lines.append((dp.relative_to(ROOT).as_posix() or ".") + "/" + name)
    return "\\n".join(lines)
tree_path.write_text(tree_lines(), encoding="utf-8")
# Markdown 摘要
hdr = ["# Code Inventory", "", f"- Root: {ROOT}", f"- TS: {TS}", f"- Files: {len(files)}", ""]
tbl = ["| # | path | size(bytes) | sha256 |","|---:|:-----|-----------:|:------|"]
for i,x in enumerate(files,1):
    tbl.append(f"| {i} | `{x[path]}` | {x[size]} | `{x[sha256]}` |")
md_path.write_text("\\n".join(hdr+tbl)+ "\\n", encoding="utf-8")
print("[OK] Wrote:", manifest_json, md_path, tree_path, filelist_path)
