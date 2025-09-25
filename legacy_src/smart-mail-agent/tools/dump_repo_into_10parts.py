#!/usr/bin/env python3
# 檔案位置：tools/dump_repo_into_10parts.py
# 模組用途：掃描專案文字檔，平衡切分為 10 份輸出文本，供人工貼回審閱
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

# 可調參數
N_PARTS = 10
OUTDIR = Path("share/dump_parts")
MAX_BYTES_PER_FILE = 2_000_000  # 單一檔案超過此大小視為大檔，排除
INCLUDE_EXTS = {
    ".py",
    ".sh",
    ".bash",
    ".zsh",
    ".bat",
    ".ps1",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".json",
    ".md",
    ".rst",
    ".txt",
    ".csv",
    ".sql",
    ".env",
    ".env.example",
    ".dockerfile",
    ".service",
    ".properties",
}
INCLUDE_BASENAMES = {
    "Dockerfile",
    "Makefile",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    "requirements.txt",
    "pyproject.toml",
    "Pipfile",
    "Pipfile.lock",
    "setup.cfg",
    "setup.py",
    "README",
    "README.md",
    "LICENSE",
}
EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "node_modules",
    "reports",
    ".cache",
    ".eggs",
    ".tox",
    "share",
}
BINARY_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".webp",
    ".svg",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".ico",
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".rar",
    ".bin",
    ".mp3",
    ".wav",
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
}


def is_binary_path(p: Path) -> bool:
    if p.suffix.lower() in BINARY_EXTS:
        return True
    try:
        with p.open("rb") as f:
            chunk = f.read(8192)
        if b"\x00" in chunk:
            return True
        # 簡單偵測非文字比例
        nontext = sum(b > 127 and b < 255 for b in chunk)
        if len(chunk) and (nontext / len(chunk) > 0.30):
            return True
    except Exception:
        return True
    return False


def should_include(p: Path) -> bool:
    if not p.is_file():
        return False
    if any(part in EXCLUDE_DIRS for part in p.parts):
        return False
    if p.name in INCLUDE_BASENAMES:
        return True
    ext = p.suffix.lower()
    if ext in INCLUDE_EXTS:
        return True
    return False


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_files(root: Path) -> Tuple[List[Path], List[Tuple[str, str]]]:
    included: List[Path] = []
    excluded: List[Tuple[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # 過濾目錄
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            p = Path(dirpath) / fn
            rel = p.relative_to(root)
            # 濾除明顯二進位與超大檔
            if is_binary_path(p):
                excluded.append((str(rel), "binary_or_unreadable"))
                continue
            if p.stat().st_size > MAX_BYTES_PER_FILE:
                excluded.append((str(rel), "too_large"))
                continue
            if should_include(p):
                included.append(p)
            else:
                excluded.append((str(rel), "not_included_ext"))
    # 穩定排序：先路徑、後尺寸
    included.sort(key=lambda x: (str(x.relative_to(root)).lower(), x.stat().st_size))
    return included, excluded


def assign_parts(files: List[Path], root: Path) -> List[List[Path]]:
    # 使用「最小堆」式的平衡分配：每次把下一檔放到目前總大小最小的一份
    import heapq

    parts: List[List[Path]] = [[] for _ in range(N_PARTS)]
    heaps = [(0, i) for i in range(N_PARTS)]  # (bytes, index)
    heapq.heapify(heaps)
    sizes = [0] * N_PARTS
    for p in files:
        size = p.stat().st_size
        total, idx = heapq.heappop(heaps)
        parts[idx].append(p)
        sizes[idx] += size
        heapq.heappush(heaps, (sizes[idx], idx))
    return parts


def write_parts(parts: List[List[Path]], root: Path) -> Dict[str, any]:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    meta = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "root": str(root.resolve()),
        "parts": [],
        "total_files": sum(len(x) for x in parts),
        "note": "使用 -----8<----- FILE: / END 標記分割檔案",
    }
    for i, group in enumerate(parts, start=1):
        outp = OUTDIR / f"part_{i:02d}.txt"
        total_bytes = sum(p.stat().st_size for p in group)
        with outp.open("w", encoding="utf-8", newline="\n") as w:
            header = (
                f"# Dump Part {i:02d}/10  root={root}  files={len(group)}  bytes={total_bytes}\n"
            )
            w.write(header)
            for p in group:
                rel = p.relative_to(root)
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                except Exception as e:
                    content = f"<<READ_ERROR {e}>>"
                sha = sha256_of(p)
                size = p.stat().st_size
                w.write(f"-----8<----- FILE: {rel}  SHA256:{sha}  BYTES:{size} -----\n")
                w.write(content)
                if not content.endswith("\n"):
                    w.write("\n")
                w.write(f"-----8<----- END {rel} -----\n")
        meta["parts"].append({"path": str(outp), "files": len(group), "bytes": total_bytes})
    with (OUTDIR / "README.txt").open("w", encoding="utf-8") as f:
        f.write(
            "將 part_01.txt ~ part_10.txt 依序貼回對話，我會據此重建並比對本機與 GitHub 殘缺版本。\n"
        )
    return meta


def main() -> int:
    root = Path(os.environ.get("PROJECT_DIR") or ".").resolve()

    # 若指定目錄不是專案，嘗試往上找
    def looks_like_repo(p: Path) -> bool:
        return (p / ".git").exists() and ((p / "src").exists() or (p / "pyproject.toml").exists())

    if not looks_like_repo(root):
        cur = Path.cwd().resolve()
        while True:
            if looks_like_repo(cur):
                root = cur
                break
            if cur.parent == cur:
                break
            cur = cur.parent
    if not looks_like_repo(root):
        print("找不到專案根：請在專案內或設 PROJECT_DIR 後再執行", file=sys.stderr)
        return 2

    included, excluded = collect_files(root)
    parts = assign_parts(included, root)
    meta = write_parts(parts, root)
    # 另存索引檔
    index = {
        "generated_at": meta["generated_at"],
        "root": meta["root"],
        "included": [
            {
                "path": str(p.relative_to(root)),
                "bytes": p.stat().st_size,
                "sha256": sha256_of(p),
                "mtime": int(p.stat().st_mtime),
            }
            for p in included
        ],
        "excluded": [{"path": path, "reason": reason} for path, reason in excluded],
        "parts": meta["parts"],
    }
    (OUTDIR / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("OK 產生完成於：", OUTDIR)
    for p in meta["parts"]:
        print(p["path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
