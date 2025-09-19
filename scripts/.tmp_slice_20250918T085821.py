import json, os, math, pathlib, hashlib, textwrap
from pathlib import Path
ROOT = Path.cwd()
STATUS = ROOT / "reports_auto/status"
OUTDIR = ROOT / "reports_auto/slices_20250918T085821"
LOG = ROOT / "reports_auto/logs/inventory_slicer_20250918T085821.log"
MANIFEST = Path("reports_auto/status/CODE_MANIFEST_20250918T083203.json")
MAXB = 90000  # 90KB per slice to stay under chat paste limits
data = json.loads(MANIFEST.read_text("utf-8"))
files = data.get("files", [])
# --- 基本摘要 ---
ext_cnt = {}
dir_cnt = {}
for x in files:
    p = x.get("path","")
    ext = Path(p).suffix.lower()
    ext_cnt[ext] = ext_cnt.get(ext,0)+1
    d = str(Path(p).parent).replace("\\\\","/")
    dir_cnt[d] = dir_cnt.get(d,0)+1
files_sorted_sz = sorted(files, key=lambda z: (z.get("size",-1), z.get("path","")), reverse=True)
def top_k(d, k=50):
    return sorted(d.items(), key=lambda t:(t[1], t[0]), reverse=True)[:k]
sum_md = OUTDIR / "SUMMARY.md"
sum_md.write_text("\\n".join([
    "# Inventory Summary",
    f"- Root: {data.get(\"root\")}",
    f"- TS(manifest): {data.get(\"ts\")}",
    f"- Files: {data.get(\"count\")}",
    "", "## By Extension (Top 50)", "| ext | count |", "|:--|--:|",
    *[f"| `{k or \"(none)\"}` | {v} |" for k,v in top_k(ext_cnt,50)],
    "", "## By Directory (Top 50)", "| dir | count |", "|:--|--:|",
    *[f"| `{k}` | {v} |" for k,v in top_k(dir_cnt,50)],
    "", "## Top Big Files (Top 200)", "| # | path | size | sha256(head) |", "|--:|:-----|---:|:-------------|",
    *[f"| {i+1} | `{x.get(\"path\")}` | {x.get(\"size\")} | `{x.get(\"sha256\")[:12]}` |" for i,x in enumerate(files_sorted_sz[:200])],
]), encoding="utf-8")
# --- 切片工具 ---
def write_slices(lines, prefix, ext):
    buf=[]; size=0; idx=1; paths=[]
    for line in lines:
        b=(line+"\\n").encode("utf-8")
        if size+len(b) > MAXB and buf:
            out=OUTDIR / f"{prefix}_{idx:04d}.{ext}"; out.write_text("".join(buf), "utf-8"); paths.append(out); buf=[]; size=0; idx+=1
        buf.append(line+"\\n"); size+=len(b)
    if buf:
        out=OUTDIR / f"{prefix}_{idx:04d}.{ext}"; out.write_text("".join(buf), "utf-8"); paths.append(out)
    return paths
# --- 產出三種切片：.md / .jsonl / .txt ---
md_hdr=["| # | path | size(bytes) | sha256 |","|---:|:-----|-----------:|:------|"]
md_rows=[f"| {i} | `{x.get(\"path\")}` | {x.get(\"size\")} | `{x.get(\"sha256\")}` |" for i,x in enumerate(files,1)]
md_paths = write_slices(md_hdr+md_rows, "INVENTORY_TABLE", "md")
jsonl_rows=[json.dumps({"path":x.get("path"),"size":x.get("size"),"sha":(x.get("sha256") or "")[:12]}, ensure_ascii=False) for x in files]
jsonl_paths = write_slices(jsonl_rows, "INVENTORY_MIN", "jsonl")
txt_rows=[x.get("path","") for x in files]
txt_paths = write_slices(txt_rows, "INVENTORY_PATHS", "txt")
# 索引檔
index_md = OUTDIR / "INDEX.md"
def rel(p): return p.relative_to(ROOT).as_posix()
index_md.write_text("\\n".join([
    "# Upload Guide",
    "", "把下列任一小檔貼到聊天視窗（建議先貼 .jsonl 或 .txt）。", "", "## Generated Files:", "" ,
    "### SUMMARY", f"- {rel(sum_md)}",
    "### INVENTORY_TABLE (Markdown slices)", *[f\"- {rel(p)}\" for p in md_paths],
    "### INVENTORY_MIN (JSONL slices)", *[f\"- {rel(p)}\" for p in jsonl_paths],
    "### INVENTORY_PATHS (TXT slices)", *[f\"- {rel(p)}\" for p in txt_paths],
]), encoding="utf-8")
print("[OK] wrote", rel(sum_md), rel(index_md))
