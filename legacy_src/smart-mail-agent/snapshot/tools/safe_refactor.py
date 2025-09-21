#!/usr/bin/env python3
import json
import re
import shutil
from pathlib import Path

ROOT = Path(".").resolve()
SRC = ROOT / "src"
CANON = "smart_mail_agent"
ALIAS_DIRS = [SRC / "utils", SRC / "spam", SRC / "patches", SRC / "modules"]
MAP_DIR = {
    SRC / "utils": SRC / CANON / "utils",
    SRC / "spam": SRC / CANON / "spam",
    SRC / "patches": SRC / CANON / "patches",
    SRC / "modules": SRC / CANON / "features/modules_legacy",
}
REWRITE = [
    (re.compile(r"(?m)^(from)\s+utils(\b)"), r"\1 smart_mail_agent.utils\2"),
    (re.compile(r"(?m)^(import)\s+utils(\b)"), r"\1 smart_mail_agent.utils\2"),
    (re.compile(r"(?m)^(from)\s+spam(\b)"), r"\1 smart_mail_agent.spam\2"),
    (re.compile(r"(?m)^(import)\s+spam(\b)"), r"\1 smart_mail_agent.spam\2"),
    (re.compile(r"(?m)^(from)\s+patches(\b)"), r"\1 smart_mail_agent.patches\2"),
    (re.compile(r"(?m)^(import)\s+patches(\b)"), r"\1 smart_mail_agent.patches\2"),
    (re.compile(r"(?m)^(from)\s+modules(\b)"), r"\1 smart_mail_agent.features.modules_legacy\2"),
    (re.compile(r"(?m)^(import)\s+modules(\b)"), r"\1 smart_mail_agent.features.modules_legacy\2"),
]


def py_files(p: Path):
    return [x for x in p.rglob("*.py") if x.is_file()]


def move_aliases(plan_only=False):
    moves = []
    for d in ALIAS_DIRS:
        if not d.exists():
            continue
        target = MAP_DIR[d]
        for f in py_files(d):
            rel = f.relative_to(d)
            dst = target / rel
            moves.append((f, dst))
            if not plan_only:
                dst.parent.mkdir(parents=True, exist_ok=True)
                if f.resolve() != dst.resolve():
                    shutil.move(str(f), str(dst))
    return moves


def rewrite_imports():
    touched = []
    for f in py_files(SRC):
        txt = f.read_text(encoding="utf-8", errors="ignore")
        new = txt
        for pat, rep in REWRITE:
            new = pat.sub(rep, new)
        if new != txt:
            f.write_text(new, encoding="utf-8")
            touched.append(str(f))
    return touched


def write_compat():
    for d, target in {
        SRC / "utils": "smart_mail_agent.utils",
        SRC / "spam": "smart_mail_agent.spam",
        SRC / "patches": "smart_mail_agent.patches",
        SRC / "modules": "smart_mail_agent.features.modules_legacy",
    }.items():
        d.mkdir(parents=True, exist_ok=True)
        (d / "__init__.py").write_text(
            f"from {target} import *  # noqa: F401,F403\n", encoding="utf-8"
        )


def main():
    plan = {"moves": [], "rewrites": []}
    moves = move_aliases(plan_only=True)
    plan["moves"] = [{"src": str(a), "dst": str(b)} for a, b in moves]
    Path("refactor_plan.json").write_text(
        json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    move_aliases(plan_only=False)
    rew = rewrite_imports()
    plan["rewrites"] = rew
    Path("refactor_plan.json").write_text(
        json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_compat()
    print(f"moved: {len(moves)} files; rewritten imports: {len(rew)} files")


if __name__ == "__main__":
    main()
