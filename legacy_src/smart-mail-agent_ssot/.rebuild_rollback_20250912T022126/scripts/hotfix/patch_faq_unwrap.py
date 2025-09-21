import os, re, shutil, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parents[2]
STAMP = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
BACKUP_ROOT = ROOT / "scripts" / "_backup" / f"patch_faq_unwrap_{STAMP}"
BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

EXCLUDES = {".git",".hg",".svn","__pycache__","node_modules",".venv","venv","env","data","db","reports_auto","scripts/_backup","scripts/hotfix"}

def skip_dir(p: pathlib.Path)->bool:
    parts=set(p.parts)
    if "scripts" in parts and "_backup" in parts: return True
    return any(e in parts for e in EXCLUDES)

# 兩個 LHS 變數，RHS 含 faq/FAQ/answer/get_answer/qa/kb/knowledge 的呼叫；允許多行
PAT = re.compile(
    r'^([ \t]*)'                   # indent
    r'([A-Za-z_]\w*)\s*,\s*([A-Za-z_]\w*)\s*=\s*'   # v1, v2 =
    r'((?:.|\n)*?(?:faq|FAQ|answer|get_answer|qa|kb|knowledge)[^\n]*?\([^)]*\))',  # call(...)
    flags=re.M
)

def patch_text(s: str)->str:
    def repl(m):
        indent, v1, v2, call = m.groups()
        tmp = f"__faq_res_{v1}_{v2}"
        return (
            f"{indent}{tmp} = {call}\n"
            f"{indent}try:\n"
            f"{indent}    {v1}, {v2} = {tmp}\n"
            f"{indent}except Exception:\n"
            f"{indent}    {v1} = getattr({tmp}, 'text', str({tmp}))\n"
            f"{indent}    {v2} = getattr({tmp}, 'score', getattr({tmp}, 'confidence', None))\n"
        )
    return PAT.sub(repl, s)

changed=scanned=0
for root, dirs, files in os.walk(ROOT):
    p=pathlib.Path(root)
    dirs[:] = [d for d in dirs if not skip_dir(p / d)]
    if skip_dir(p): continue
    for fn in files:
        if not fn.endswith(".py"): continue
        py = p / fn
        if "scripts/hotfix" in str(py).replace("\\","/"): continue
        try:
            src = py.read_text(encoding="utf-8")
        except Exception:
            continue
        scanned += 1
        dst = patch_text(src)
        if dst != src:
            backup = BACKUP_ROOT / py.relative_to(ROOT)
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(py, backup)
            py.write_text(dst, encoding="utf-8")
            print(f"[patched] {py}")
            changed += 1

print(f"[DONE] scanned={scanned} changed={changed} backup_at={BACKUP_ROOT}")
