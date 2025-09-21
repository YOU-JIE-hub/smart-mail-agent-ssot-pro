from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")


def write(p: Path, s: str) -> None:
    if not s.endswith("\n"):
        s += "\n"
    p.write_text(s, encoding="utf-8")


def is_pkg_dir(d: Path) -> bool:
    return (d / "__init__.py").exists()


def module_name_for_file(f: Path) -> Optional[str]:
    """推導檔案的模組路徑（有 __init__.py 鏈路才算套件）。"""
    f = f.resolve()
    if not f.is_file() or f.suffix != ".py":
        return None
    parts: List[str] = []
    d = f.parent
    # 往上收集 __init__.py 連續存在的層級
    while d != ROOT and is_pkg_dir(d):
        parts.append(d.name)
        d = d.parent
    if not parts:
        return None
    parts.reverse()
    mod = ".".join(parts + [f.stem])
    return mod


def resolve_relative(current_mod: str, rel_level: int, rel_module: Optional[str]) -> Optional[str]:
    """把相對匯入（level>0）轉為絕對模組字串。"""
    base = current_mod.split(".")[:-1]  # 去掉檔名
    if rel_level > len(base):
        return None
    base = base[: len(base) - rel_level + 1]
    if rel_module:
        base += rel_module.split(".")
    return ".".join(base)


def guess_exports_from_file(mod_file: Path) -> List[str]:
    """靜態解析：優先讀 __all__；否則取頂層 def/class 名稱（去掉前導底線）。"""
    try:
        tree = ast.parse(read(mod_file))
    except Exception:
        return []
    # 讀 __all__
    exports: List[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "__all__":
                    try:
                        v = ast.literal_eval(node.value)
                        if isinstance(v, (list, tuple)):
                            exports = [str(x) for x in v if isinstance(x, str)]
                            return [n for n in exports if not n.startswith("_")]
                    except Exception:
                        pass
    # 沒有 __all__ → def/class
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                exports.append(node.name)
    # 去重、排序
    return sorted(set(exports))


def find_module_file(abs_module: str) -> Optional[Path]:
    """
    把 'pkg.sub.mod' 映射到專案內的檔案：
    1) <ROOT>/pkg/sub/mod.py
    2) <ROOT>/pkg/sub/mod/__init__.py
    """
    p = ROOT / Path(*abs_module.split("."))
    py = p.with_suffix(".py")
    if py.exists():
        return py
    init = p / "__init__.py"
    if init.exists():
        return init
    return None


def star_import_replacements(f: Path) -> Optional[str]:
    """
    回傳替換後全文；若無修改傳回 None。
    只處理 AST ImportFrom + alias=='*' 的情況。
    """
    src = read(f)
    try:
        tree = ast.parse(src)
    except Exception:
        # 解析不了就不碰（交給 black/ruff 先救）
        return None

    current_mod = module_name_for_file(f)
    # 收集所有 star import 節點
    stars: List[ast.ImportFrom] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if any(getattr(a, "name", "") == "*" for a in node.names):
                stars.append(node)
    if not stars:
        return None

    # 逐一建立替換片段
    # 以行為單位替換：用 end_lineno/col 需 Python 3.8+（這裡 3.10 OK）
    lines = src.splitlines(keepends=True)
    # 先把要換的範圍標記出來
    patches: List[tuple[int, int, str]] = (
        []
    )  # (start_line_idx, end_line_idx_exclusive, replacement)

    for node in stars:
        start = node.lineno - 1
        end = node.end_lineno  # exclusive index
        indent = ""
        # 取縮排
        try:
            indent = lines[start][: len(lines[start]) - len(lines[start].lstrip())]
        except Exception:
            pass

        # 算出絕對模組名
        abs_mod: Optional[str] = None
        if node.level and node.level > 0:
            if current_mod:
                abs_mod = resolve_relative(current_mod, node.level, node.module)
        else:
            abs_mod = node.module

        replacement = None
        if abs_mod:
            mod_file = find_module_file(abs_mod)
            if mod_file:
                names = guess_exports_from_file(mod_file)
                if names:
                    joined = (",\n" + indent + "    ").join(names)
                    replacement = (
                        f"{indent}from {abs_mod} import (\n"
                        f"{indent}    {joined}\n"
                        f"{indent})\n"
                        f"{indent}__all__ = [{', '.join(repr(n) for n in names)}]\n"
                    )

        if replacement is None:
            # 降級方案：保留 * 並加上 noqa，避免卡關
            # 重新用原始行文字（避免刪掉註解）
            original = "".join(lines[start:end])
            if "# noqa" not in original:
                original = original.rstrip("\n") + "  # noqa: F403,F401\n"
            replacement = original

        patches.append((start, end, replacement))

    # 依開始行號由大到小替換，避免位移影響
    patches.sort(key=lambda x: x[0], reverse=True)
    for s_idx, e_idx, rep in patches:
        lines[s_idx:e_idx] = [rep]

    return "".join(lines)


def main() -> None:
    changed = 0
    for p in ROOT.rglob("*.py"):
        # 跳過產物與快取
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith(
            (
                "out/",
                "outputs/",
                "share/",
                ".git/",
                ".ruff_cache/",
                ".pytest_cache/",
                "__pycache__/",
            )
        ):
            continue
        new_src = star_import_replacements(p)
        if new_src is not None and new_src != read(p):
            write(p, new_src)
            changed += 1
            print(f"[fix] star-import -> explicit/noqa: {rel}")
    print(f"[done] modified files: {changed}")


if __name__ == "__main__":
    main()
