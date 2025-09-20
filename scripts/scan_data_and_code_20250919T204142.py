import os, re, json, ast, hashlib, time, traceback, subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# ---------- 設定 ----------
ROOTS = os.environ.get("ROOTS","").split()
OUTDIR = Path(os.environ.get("OUTDIR","."))
OUT_JSON = OUTDIR / "data_path_audit.json"
OUT_MD   = OUTDIR / "data_path_audit.md"

DATA_EXTS = [
    ".jsonl",".ndjson",".json",".csv",".tsv",".parquet",".feather",".arrow",
    ".txt",".yaml",".yml",".ini",".cfg",".xml",".sqlite",".db",
    ".pkl",".joblib",".npz",".npy",".h5",".bin"
]
# 直接從原始碼撈出「看起來像檔案路徑」的字串（副檔名白名單）
PATH_RE = re.compile(
    r"""(?P<q>['"])(?P<p>(?:~|\.{0,2}/|/|[A-Za-z]:\\)[^'"]+\.(?:jsonl|ndjson|json|csv|tsv|parquet|feather|arrow|txt|yaml|yml|ini|cfg|xml|sqlite|db|pkl|joblib|npz|npy|h5|bin))(?P=q)""",
    re.IGNORECASE
)

# 嘗試把 Linux 路徑轉成 Windows 的 \\wsl.localhost\ 路徑
def to_win_path(p: Path) -> Optional[str]:
    try:
        out = subprocess.check_output(["wslpath","-w",str(p)], stderr=subprocess.DEVNULL).decode().strip()
        return out
    except Exception:
        # 自行拼 wsl UNC
        parts = p.as_posix()
        if parts.startswith("/home/"):
            return r"\\wsl.localhost\Ubuntu-22.04" + parts.replace("/", "\\")
        return None

def sha256_head(fp: Path, bytes_to_read: int = 1024*1024) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with fp.open("rb") as f:
            h.update(f.read(bytes_to_read))
        return h.hexdigest()
    except Exception:
        return None

def safe_rel(p: Path, root: Path) -> str:
    try:
        return p.relative_to(root).as_posix()
    except Exception:
        return p.as_posix()

def walk_files(root: Path) -> List[Path]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # 可在這裡排除某些資料夾（如 .git / .venv / node_modules / artifacts…）
        base = Path(dirpath).name
        if base in {".git","venv",".venv","__pycache__","node_modules","dist","build","artifacts","artifacts_inbox","artifacts_prod","models","weights","datasets","data"}:
            # 仍可能想找 data/；若你要包含 data/，把上面 "data" 移除即可
            pass
        for fn in filenames:
            out.append(Path(dirpath) / fn)
    return out

def is_data_file(p: Path) -> bool:
    return p.suffix.lower() in DATA_EXTS

def collect_fs_items(roots: List[Path]) -> List[Dict[str,Any]]:
    items = []
    for r in roots:
        if not r.exists(): 
            continue
        for p in walk_files(r):
            if is_data_file(p):
                try:
                    st = p.stat()
                    items.append({
                        "type": "fs_data",
                        "path": p.as_posix(),
                        "root": r.as_posix(),
                        "rel": safe_rel(p, r),
                        "size": st.st_size,
                        "mtime": int(st.st_mtime),
                        "sha256_head": sha256_head(p),
                        "win_path": to_win_path(p),
                    })
                except Exception:
                    pass
    return items

# 解析 .py，找出字串中看起來像檔案路徑，並嘗試解析為實際存在的檔案
def resolve_candidate(code_file: Path, s: str, roots: List[Path]) -> Tuple[str, Optional[str], Optional[str], Optional[int], Optional[str]]:
    raw = s
    # ~ / 環境變數展開
    s_exp = os.path.expanduser(os.path.expandvars(s))
    candidates = []
    # 絕對或 Windows 絕對：直接嘗試
    if s_exp.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:\\", s_exp):
        candidates.append(Path(s_exp))
    # 相對於原始碼檔所在資料夾
    candidates.append((code_file.parent / s_exp).resolve())
    # 相對於各個 root
    for r in roots:
        candidates.append((r / s_exp).resolve())
    # 找第一個存在的
    for c in candidates:
        try:
            if c.exists() and c.is_file():
                st = c.stat()
                return raw, c.as_posix(), to_win_path(c), st.st_size, sha256_head(c)
        except Exception:
            continue
    return raw, None, None, None, None

def collect_code_refs(roots: List[Path]) -> List[Dict[str,Any]]:
    out = []
    for r in roots:
        if not r.exists(): 
            continue
        for p in walk_files(r):
            if p.suffix.lower() != ".py":
                continue
            try:
                txt = p.read_text("utf-8", errors="ignore")
            except Exception:
                continue
            # 1) Regex 直接撈
            for m in PATH_RE.finditer(txt):
                lit = m.group("p")
                raw, abs_lin, win_lin, sz, sh = resolve_candidate(p, lit, roots)
                out.append({
                    "type":"code_ref",
                    "code_file": p.as_posix(),
                    "line": txt.count("\n", 0, m.start()) + 1,
                    "literal": raw,
                    "resolved": abs_lin,
                    "resolved_win": win_lin,
                    "exists": abs_lin is not None,
                    "size": sz,
                    "sha256_head": sh,
                })
            # 2) AST 萃取 Constant 字串（副檔名白名單）
            try:
                tree = ast.parse(txt)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        s = node.value
                        if any(s.lower().endswith(ext) for ext in DATA_EXTS):
                            raw, abs_lin, win_lin, sz, sh = resolve_candidate(p, s, roots)
                            out.append({
                                "type":"code_ref",
                                "code_file": p.as_posix(),
                                "line": getattr(node, "lineno", None),
                                "literal": raw,
                                "resolved": abs_lin,
                                "resolved_win": win_lin,
                                "exists": abs_lin is not None,
                                "size": sz,
                                "sha256_head": sh,
                            })
            except Exception:
                pass
    return out

def main():
    roots = [Path(x).resolve() for x in ROOTS if x]
    OUTDIR.mkdir(parents=True, exist_ok=True)
    fs_items = collect_fs_items(roots)
    code_refs = collect_code_refs(roots)

    # 合併概覽
    summary = {
        "roots": [r.as_posix() for r in roots],
        "counts": {
            "fs_data": len(fs_items),
            "code_refs": len(code_refs),
            "code_refs_existing": sum(1 for x in code_refs if x.get("exists")),
        },
        "generated_at": int(time.time()),
    }
    payload = {"summary": summary, "fs_data": fs_items, "code_refs": code_refs}
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")

    # 產 Markdown（方便人工看）
    lines = []
    lines.append(f"# Data & Path Audit ({time.strftime('%Y-%m-%d %H:%M:%S')})")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Roots: {', '.join(summary['roots'])}")
    lines.append(f"- FS data files: **{summary['counts']['fs_data']}**")
    lines.append(f"- Code path refs: **{summary['counts']['code_refs']}**  (existing: **{summary['counts']['code_refs_existing']}**)")
    lines.append("")
    lines.append("## Filesystem data (top 200 by size)")
    topfs = sorted(fs_items, key=lambda x: x.get("size") or 0, reverse=True)[:200]
    for it in topfs:
        lines.append(f"- `{it['path']}`  \n  size={it['size']:,}  sha256_head={it.get('sha256_head')}  \n  win=`{it.get('win_path')}`")
    lines.append("")
    lines.append("## Code references (first 300)")
    for it in code_refs[:300]:
        flag = "✅" if it.get("exists") else "❌"
        lines.append(f"- {flag} {it['code_file']}:{it.get('line')}  →  `{it['literal']}`")
        if it.get("resolved"):
            lines.append(f"    - resolved: `{it['resolved']}` (size={it.get('size')})")
            if it.get("resolved_win"):
                lines.append(f"    - win: `{it['resolved_win']}`")
    OUT_MD.write_text("\n".join(lines), "utf-8")

    print("[OK] JSON:", OUT_JSON.as_posix())
    print("[OK] Markdown:", OUT_MD.as_posix())

if __name__ == "__main__":
    main()
