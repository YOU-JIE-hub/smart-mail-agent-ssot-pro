from __future__ import annotations

import importlib
import os
import re
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))  # 讓 repo 根目錄可被 import

PY_EXT = (".py",)


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")


def write_text(p: Path, s: str) -> None:
    # 保留結尾換行（給 EOF fixer 友善）
    if not s.endswith("\n"):
        s += "\n"
    p.write_text(s, encoding="utf-8")


def all_py_files() -> list[Path]:
    ignore_dirs = {
        ".git",
        ".venv",
        "venv",
        ".mypy_cache",
        ".ruff_cache",
        "__pycache__",
        ".pytest_cache",
        ".cache",
        "out",
        "outputs",
        "share",
        "tmp_attachments",
        "report_parts_",
        "report_top10_",
        "repo_",
    }
    out = []
    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT).as_posix()
        if any(seg.startswith(tuple(ignore_dirs)) for seg in rel.split("/")):
            continue
        out.append(p)
    return out


def fix_apply_patch():
    p = ROOT / "apply_patch_r9.py"
    if not p.exists():
        return False
    s = read_text(p)
    orig = s
    # 1) 將「行首為非 ASCII」的中文敘述行註解掉，避免語法解析
    new_lines = []
    for line in s.splitlines():
        if re.match(r"^\s*[^\x00-\x7F]", line):
            # 轉成註解
            line = re.sub(r"^(\s*)", r"\1# ", line)
        new_lines.append(line)
    s = "\n".join(new_lines)
    # 2) 補齊未關閉的 r"""（簡單檢查配對數）
    triple = re.findall(r'(^|[^\\])("""|\'\'\')', s)
    if len(triple) % 2 == 1:
        s += '\n"""\n'
    if s != orig:
        write_text(p, s)
        print("[fix] apply_patch_r9.py")
        return True
    return False


STAR_RE = re.compile(r"^from\s+([.\w]+)\s+import\s+\*\s*(#.*)?$", re.M)


def discover_names(mod: ModuleType) -> list[str]:
    names = getattr(mod, "__all__", None)
    if names:
        return sorted([n for n in names if not n.startswith("_")])
    # fallback: dir 過濾掉私有與模組
    out = []
    for n in dir(mod):
        if n.startswith("_"):
            continue
        try:
            if isinstance(getattr(mod, n), ModuleType):
                continue
        except Exception:
            pass
        out.append(n)
    return sorted(out)


def replace_star_imports(p: Path) -> bool:
    s = read_text(p)
    changed = False
    # 可能有多個 star import，逐一替換
    while True:
        m = STAR_RE.search(s)
        if not m:
            break
        modname = m.group(1)
        try:
            mod = importlib.import_module(modname)
        except Exception as e:
            print(f"[warn] cannot import {modname} referenced by {p}: {e}")
            # 跳過這個 star，避免壞掉
            s = (
                s[: m.start()]
                + m.group(0).replace("import *", "import *  # noqa: F403,F401")
                + s[m.end() :]
            )
            changed = True
            continue
        names = discover_names(mod)
        if not names:
            # 沒有可匯出的名稱，一樣降級為 noqa
            repl = f"from {modname} import *  # noqa: F403,F401"
        else:
            joined_names = ",\n    ".join(names)
            repl = f"from {modname} import (\n    {joined_names}\n)\n\n__all__ = [{', '.join(repr(n) for n in names)}]"
        s = s[: m.start()] + repl + s[m.end() :]
        changed = True
    if changed:
        write_text(p, s)
        print(f"[fix] star-import -> explicit: {p}")
    return changed


def rewrite_policy_engine_wrapper():
    p = ROOT / "src" / "smart_mail_agent" / "policy_engine.py"
    if not p.exists():
        return False
    content = '''\
"""Compatibility wrapper for `smart_mail_agent.policy_engine` via core module."""
from importlib import import_module

_core = import_module("smart_mail_agent.core.policy_engine")
apply_policies = getattr(_core, "apply_policies")
apply_policy = getattr(_core, "apply_policy", apply_policies)

__all__ = ["apply_policies", "apply_policy"]
'''
    if read_text(p) != content:
        write_text(p, content)
        print(f"[fix] rewrite wrapper: {p}")
        return True
    return False


def rewrite_internal_smoke_test():
    p = ROOT / "legacy_tests" / "internal_smoke" / "test_import_all_internal.py"
    if not p.exists():
        return False
    content = """\
import importlib
import pkgutil
import smart_mail_agent
import pytest

# 自動發現 smart_mail_agent 下面的所有可匯入模組（避免手寫重覆清單）
mods = [
    m.name
    for m in pkgutil.walk_packages(smart_mail_agent.__path__, prefix="smart_mail_agent.")
]

@pytest.mark.parametrize("mod", mods)
def test_import_module(mod: str) -> None:
    importlib.import_module(mod)
"""
    if read_text(p) != content:
        write_text(p, content)
        print("[fix] rewrite internal smoke test")
        return True
    return False


def main():
    total_changed = 0
    total_changed += bool(fix_apply_patch())
    total_changed += bool(rewrite_policy_engine_wrapper())
    total_changed += bool(rewrite_internal_smoke_test())

    # 逐檔消滅 star import
    for f in all_py_files():
        try:
            if replace_star_imports(f):
                total_changed += 1
        except Exception as e:
            print(f"[warn] fail on {f}: {e}")
    print(f"[done] modified files: {total_changed}")


if __name__ == "__main__":
    main()
