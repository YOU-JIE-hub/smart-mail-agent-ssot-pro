#!/usr/bin/env bash
source .sma_tools/env_guard.sh
set -euo pipefail

# ---- 參數（可用環境變數覆蓋）----
: "${INCLUDE_DIRS:=src scripts .sma_tools}"              # 只掃這些資料夾
: "${ALLOW_EXT:=.py,.sh,.yml,.yaml,.json,.toml,.ini,.cfg,.md}"
: "${MAX_FILE_KB:=200}"                                  # 單檔最大內嵌大小
: "${FILE_LIMIT:=20}"                                    # 匯出檔案數上限（重點）
: "${PRIORITY_GLOBS:=README.md;src/**/__init__.py;scripts/sma_*;.sma_tools/*.yml}"
: "${SORT_MODE:=size}"                                   # size | alpha
: "${TARGET_PART_MB:=1}"                                 # 估算要切幾份的目標大小
: "${FORCE_PARTS:=}"                                     # 固定份數（空=自動）
: "${DRY_RUN:=0}"                                        # 1=只顯示規劃不落盤
: "${DEBUG:=0}"
: "${ROOT_DIR:=$PWD}"
: "${OUT_DIR:=$PWD/export}"

python - <<'PY'
from __future__ import annotations
import os, sys, math, pathlib, zipfile, traceback, fnmatch

def dbg(*a):
    if os.environ.get("DEBUG","0")=="1": print("[DEBUG]", *a, file=sys.stderr)

ROOT   = pathlib.Path(os.environ.get("ROOT_DIR", os.getcwd())).resolve()
OUTDIR = pathlib.Path(os.environ.get("OUT_DIR", str(ROOT / "export"))).resolve()
OUTDIR.mkdir(parents=True, exist_ok=True)
LOGTXT = (ROOT / "reports_auto" / "export_log.txt"); LOGTXT.parent.mkdir(parents=True, exist_ok=True)

INCLUDE_DIRS = [p for p in os.environ.get("INCLUDE_DIRS","src scripts .sma_tools").split() if p]
ALLOW_EXT    = {e.strip().lower() for e in os.environ.get("ALLOW_EXT",".py,.sh,.yml,.yaml,.json,.toml,.ini,.cfg,.md").split(",")}
MAX_FILE_B   = int(os.environ.get("MAX_FILE_KB","200")) * 1024
FILE_LIMIT   = max(1, int(os.environ.get("FILE_LIMIT","20")))
PRIORITY_GLOBS = [g for g in os.environ.get("PRIORITY_GLOBS","").split(";") if g]
SORT_MODE    = os.environ.get("SORT_MODE","size")
TARGET_PART_B= max(1, int(float(os.environ.get("TARGET_PART_MB","1")) * 1024 * 1024))
FORCE_PARTS  = os.environ.get("FORCE_PARTS","").strip()
DRY_RUN      = os.environ.get("DRY_RUN","0")=="1"

EXCLUDE_DIRS = {
    ".git",".svn",".hg",".venv","venv","node_modules","__pycache__",
    "data","reports_auto","artifacts","artifacts_prod","artifacts_sa_text",
    "export",".mypy_cache",".pytest_cache",".idea",".vscode",".DS_Store"
}

def in_scope(p: pathlib.Path)->bool:
    rel = p.relative_to(ROOT).as_posix()
    parts = set(rel.split("/"))
    if any(d in parts for d in EXCLUDE_DIRS): return False
    if p.suffix.lower() not in ALLOW_EXT: return False
    return any(rel==d or rel.startswith(d+"/") for d in INCLUDE_DIRS)

# 掃描
files = []   # (rel, size_bytes, content_bytes)
skips_big, skips_io = [], []
for base in INCLUDE_DIRS:
    bp = (ROOT/base).resolve()
    if not bp.exists(): continue
    for p in bp.rglob("*"):
        if not p.is_file(): continue
        try:
            if not in_scope(p): continue
            rel = p.relative_to(ROOT).as_posix()
            lang = {
                ".py":"python",".sh":"bash",".yml":"yaml",".yaml":"yaml",
                ".json":"json",".toml":"toml",".ini":"ini",".cfg":"ini",".md":"md"
            }.get(p.suffix.lower(),"")
            txt = p.read_text(encoding="utf-8", errors="ignore")
            block = f"## {rel}  \n```{lang}\n{txt}\n```\n\n".encode("utf-8", errors="ignore")
            if len(block) > MAX_FILE_B:
                skips_big.append((rel, len(block))); continue
            files.append((rel, len(block), block))
        except Exception as e:
            skips_io.append((p.as_posix(), str(e)))

if not files:
    print("[FATAL] 無可匯出的檔案（請調整 INCLUDE_DIRS/ALLOW_EXT/EXCLUDE_DIRS）", file=sys.stderr)
    sys.exit(2)

# 優先規則：先放 priority globs 命中，再用大小或字母排序補到 FILE_LIMIT
def is_priority(rel: str)->bool:
    return any(fnmatch.fnmatch(rel, pat) for pat in PRIORITY_GLOBS)

pri = [it for it in files if is_priority(it[0])]
non = [it for it in files if not is_priority(it[0])]
# 去重（避免重複）
seen = set()
sel = []
for it in pri:
    if it[0] in seen: continue
    sel.append(it); seen.add(it[0])
# 根據 SORT_MODE 排序 non
if SORT_MODE=="alpha":
    non.sort(key=lambda x: x[0])
else:
    non.sort(key=lambda x: x[1], reverse=True)  # by size
for it in non:
    if len(sel) >= FILE_LIMIT: break
    if it[0] in seen: continue
    sel.append(it); seen.add(it[0])

# 估算分卷數
total = sum(sz for _,sz,_ in sel)
if os.environ.get("FORCE_PARTS","").strip():
    try:
        parts = max(1, int(os.environ["FORCE_PARTS"]))
    except:
        parts = max(1, math.ceil(total / TARGET_PART_B))
else:
    parts = max(1, math.ceil(total / TARGET_PART_B))
# 貪婪分桶
buckets = [{"size":0,"items":[]} for _ in range(parts)]
for it in sorted(sel, key=lambda x: x[1], reverse=True):
    b = min(buckets, key=lambda t: t["size"])
    b["items"].append(it); b["size"] += it[1]

# 清單輸出（DRY_RUN）
print(f"[PLAN] selected_files={len(sel)}/{len(files)} total_bytes={total} parts={parts}")
for i,bk in enumerate(buckets,1):
    print(f"  part {i:02d}: files={len(bk['items'])} size={bk['size']}")

if DRY_RUN:
    print("[DRY_RUN] 僅顯示規劃，不落盤")
    if skips_big:
        print(f"[SKIPPED_BIG] {len(skips_big)} files (>{int(MAX_FILE_B/1024)}KB)")
        for rel, sz in skips_big[:20]:
            print("   ", rel, sz, "bytes")
    if skips_io:
        print(f"[SKIPPED_IO] {len(skips_io)} files (read error)")
    sys.exit(0)

# 寫檔
for i,bk in enumerate(buckets,1):
    outp = OUTDIR / f"code_part_{i:03d}.md"
    with open(outp, "wb") as w:
        w.write(f"# Project Code Export (Part {i:03d}/{parts:03d})\n\n".encode())
        for rel,_,blob in sorted(bk["items"], key=lambda x: x[0]):
            w.write(blob)

# MANIFEST + ZIP
with open(OUTDIR/"MANIFEST.txt","w",encoding="utf-8") as w:
    w.write(f"SELECTED={len(sel)}/{len(files)} bytes={total} parts={parts}\n")
    w.write("PRIORITY_GLOBS="+ ";".join(PRIORITY_GLOBS)+"\n")
    for i,bk in enumerate(buckets,1):
        w.write(f"part {i:03d}\tfiles={len(bk['items'])}\tsize={bk['size']}\n")
    if skips_big:
        w.write("\n[SKIPPED_BIG]\n")
        for rel, sz in sorted(skips_big):
            w.write(f"{rel}\t{sz} bytes\n")
    if skips_io:
        w.write("\n[SKIPPED_IO]\n")
        for rel, err in skips_io:
            w.write(f"{rel}\t{err}\n")

zip_path = ROOT / "reports_auto" / "code_export_topN_v3.zip"
zip_path.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
    for p in sorted(OUTDIR.glob("code_part_*.md")):
        z.write(p, arcname=p.name)
    z.write(OUTDIR/"MANIFEST.txt", arcname="MANIFEST.txt")

print("[OK] export ->", OUTDIR.as_posix())
print("[OK] bundle ->", zip_path.as_posix())
PY
