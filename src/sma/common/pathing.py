from __future__ import annotations
import os
from pathlib import Path

LEGACY_ROOTS = [
    "/home/youjie/projects/smart-mail-agent_ssot",
    "/mnt/c/Users",  # 防止偶發貼錯 Windows 絕對路徑
]

def project_root() -> Path:
    here = Path(__file__).resolve()
    for p in [here, *here.parents]:
        if (p / "src").exists() and ((p / ".git").exists() or (p / "README.md").exists()):
            return p
    return Path.cwd()

def _translate_legacy(p: Path) -> Path:
    sp = str(p)
    for root in LEGACY_ROOTS:
        if sp.startswith(root):
            rel = sp[len(root):].lstrip("/\\")
            cand = project_root() / rel
            if cand.exists():
                return cand
    return p

def as_existing_path(value: str | None) -> Path | None:
    if not value:
        return None
    p = Path(value)
    # 1) 直接可用
    if p.exists(): return p
    # 2) 翻譯舊根
    tp = _translate_legacy(p)
    if tp.exists(): return tp
    # 3) 嘗試相對於 repo root
    rp = project_root() / value
    if rp.exists(): return rp
    return None

def env_path(name: str, default_rel: str | None = None) -> Path | None:
    v = os.getenv(name)
    p = as_existing_path(v) if v else None
    if p: return p
    if default_rel:
        cand = project_root() / default_rel
        return cand if cand.exists() else None
    return None
