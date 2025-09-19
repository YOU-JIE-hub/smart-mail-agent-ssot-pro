from __future__ import annotations
import os, sys, json, hashlib
from pathlib import Path

ROOT = Path(os.environ.get("ROOT", Path.cwd()))
OUTDIR = Path("bundles"); OUTDIR.mkdir(parents=True, exist_ok=True)
TS = os.popen("date +%Y%m%dT%H%M%S").read().strip()
CODEBOOK = OUTDIR / f"PROJECT_CODEBOOK_{TS}.md"
TREEFILE = OUTDIR / f"PROJECT_TREE_{TS}.txt"

# 視為文字的副檔名
TEXT_EXT = {
  ".py",".sh",".md",".txt",".sql",".csv",".json",".yml",".yaml",".toml",".ini",
  ".cfg",".conf",".env",".ts",".tsx",".js",".jsx",".css",".scss",".html",".xml",
  ".dockerfile",".service",".ignore",".gitignore",".gitattributes"
}
# 排除目錄
SKIP_DIRS = {".git",".venv","__pycache__","bundles",".mypy_cache",".pytest_cache",".idea",".vscode"}
# 排除大型/二進位副檔名（僅入清單，不收錄內容）
BIN_EXT = {".safetensors",".pt",".bin",".onnx",".whl",".so",".dylib",".dll",".exe",".pdf",".zip",".gz",".tgz",".xz",".7z",".rar",".jpg",".jpeg",".png",".gif",".pptx",".docx",".xlsx"}

def is_text(p: Path)->bool:
    if p.suffix.lower() in TEXT_EXT: return True
    if p.suffix.lower() in BIN_EXT: return False
    try:
        sample = p.open("rb").read(4096)
        sample.decode("utf-8")
        return True
    except Exception:
        return False

def sha256(p: Path, limit: int|None=None)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        if limit is None:
            for chunk in iter(lambda: f.read(1<<20), b""):
                h.update(chunk)
        else:
            h.update(f.read(limit))
    return h.hexdigest()

# 先輸出目錄樹
def write_tree(root: Path, outf: Path):
    lines=[]
    for d, subdirs, files in os.walk(root):
        dpath=Path(d)
        if any(x in dpath.parts for x in SKIP_DIRS): continue
        level=len(dpath.relative_to(root).parts) if dpath!=root else 0
        prefix="  " * level
        lines.append(f"{prefix}{dpath.relative_to(root) if dpath!=root else '.'}")
        for f in sorted(files):
            fp=dpath/f
            lines.append(f"{prefix}  {fp.name}")
    outf.write_text("\n".join(lines), encoding="utf-8")

write_tree(ROOT, TREEFILE)

# 大清單（包含是否納入、大小、hash）
manifest=[]
codebook_parts=[]

for d, subdirs, files in os.walk(ROOT):
    dpath=Path(d)
    if any(x in dpath.parts for x in SKIP_DIRS):
        continue
    for name in files:
        p=dpath/name
        if p.is_symlink():
            target=str(os.readlink(p))
            manifest.append({"path":str(p.relative_to(ROOT)),"type":"symlink","target":target})
            continue
        rel = str(p.relative_to(ROOT))
        size = p.stat().st_size
        ext = p.suffix.lower()
        include = True
        reason = ""
        if ext in BIN_EXT:
            include=False; reason="binary_ext"
        if size > 80*1024*1024:  # >80MB 視為大檔
            include=False; reason = (reason+"+large") if reason else "large"
        if p.parts[0]=="bundles":
            include=False; reason=(reason+"+bundles") if reason else "bundles"

        rec={"path":rel,"size":size,"sha256":None,"include":include,"reason":reason or None}
        try:
            if include:
                rec["sha256"]=sha256(p)
            else:
                rec["sha256_head"]=sha256(p, limit=1<<20)  # 首 1MB 的指紋
        except Exception as e:
            rec["error"]=f"{type(e).__name__}:{e}"
            include=False
        manifest.append(rec)

        if include and is_text(p):
            try:
                lang = (ext.lstrip(".") or "")
                content = p.read_text(encoding="utf-8", errors="replace")
                codebook_parts.append(
                    f"\n\n---\n\n## {rel}\n\n```{lang}\n{content}\n```\n"
                )
            except Exception as e:
                codebook_parts.append(
                    f"\n\n---\n\n## {rel}\n\n```\n<READ_ERROR: {e}>\n```\n"
                )

# 輸出清單 / 資產線索 / 環境快照
MANI = OUTDIR / f"BUNDLE_MANIFEST_{TS}.json"
ASSET = OUTDIR / f"ASSET_HINTS_{TS}.json"
ENVJ  = OUTDIR / f"ENV_SNAPSHOT_{TS}.json"

hints=[]
for cand in [
    "artifacts_inbox/kie1/model",
    "artifacts_kie/model",
    "../smart-mail-agent_ssot/artifacts_inbox/kie1/model",
]:
    absd = (ROOT/Path(cand)).resolve()
    if absd.exists():
        hints.append(str(absd))

asset = {
  "KIE_MODEL_DIR_env": os.environ.get("KIE_MODEL_DIR",""),
  "KIE_MODEL_DIR_hints": hints,
}

MANI.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
ASSET.write_text(json.dumps(asset, ensure_ascii=False, indent=2), encoding="utf-8")

env = {
  "python": sys.version,
  "cwd": str(ROOT),
  "env": {k:os.environ.get(k,"") for k in ["SMA_INTENT_ML_PKL","KIE_MODEL_DIR","TRANSFORMERS_OFFLINE"]},
}
ENVJ.write_text(json.dumps(env, ensure_ascii=False, indent=2), encoding="utf-8")

CODEBOOK.write_text(
  "# PROJECT CODEBOOK (all text files)\n"
  f"\n- Generated: {TS}\n- Root: {ROOT}\n"
  f"\n\n## Directory tree\n\n```\n{TREEFILE.read_text(encoding='utf-8')}\n```\n"
  + "".join(codebook_parts),
  encoding="utf-8"
)

print(json.dumps({
  "TS": TS,
  "manifest": str(MANI),
  "asset_hints": str(ASSET),
  "env_snapshot": str(ENVJ),
  "codebook": str(CODEBOOK),
  "tree": str(TREEFILE),
}, ensure_ascii=False, indent=2))
