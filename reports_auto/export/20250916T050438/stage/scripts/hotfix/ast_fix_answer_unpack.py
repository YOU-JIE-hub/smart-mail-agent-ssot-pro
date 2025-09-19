import ast, pathlib, shutil, datetime

ROOT = pathlib.Path(__file__).resolve().parents[2]
STAMP = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
BACKUP_ROOT = ROOT / "scripts" / "_backup" / f"ast_fix_answer_unpack_{STAMP}"
BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

# 僅掃描你的專案目錄（白名單）
WHITELIST = [ "scripts", "src", "sma", "app", "agents", "packages", "pipeline" ]

# 函式名關鍵字
KEYS = ("answer", "faq", "kb", "get_answer")

class Rewriter(ast.NodeTransformer):
    def __init__(self): self.changed = False

    def _need_patch(self, node: ast.Assign) -> bool:
        # 只處理形如 a,b = call(...)
        if len(node.targets) != 1: return False
        tgt = node.targets[0]
        if not isinstance(tgt, ast.Tuple) or len(tgt.elts) != 2: return False
        if not isinstance(node.value, ast.Call): return False
        # 函式名 / 屬性名包含關鍵字
        f = node.value.func
        name = None
        if isinstance(f, ast.Name):
            name = f.id
        elif isinstance(f, ast.Attribute):
            name = f.attr
        return (name is not None) and any(k in name for k in KEYS)

    def visit_Assign(self, node: ast.Assign):
        node = self.generic_visit(node)
        if not self._need_patch(node): return node

        # 目標變數
        a, b = node.targets[0].elts
        a_src = ast.unparse(a)
        b_src = ast.unparse(b)
        call_src = ast.unparse(node.value)

        # 產生安全拆包的多行程式碼
        tmp = f"__ans_tmp_{abs(hash(call_src))}"
        new_src = (
            f"{tmp} = {call_src}\n"
            f"try:\n"
            f"    {a_src}, {b_src} = {tmp}\n"
            f"except Exception:\n"
            f"    {a_src} = getattr({tmp}, 'text', str({tmp}))\n"
            f"    {b_src} = getattr({tmp}, 'score', getattr({tmp}, 'confidence', None))\n"
        )

        # 以 parse 後的多個語句替代原本一行
        new_nodes = ast.parse(new_src).body
        self.changed = True
        return new_nodes

def should_scan(p: pathlib.Path) -> bool:
    parts = p.parts
    if any(x in parts for x in (".git", ".venv", ".venv_clean", "__pycache__", "node_modules", "scripts/_backup")):
        return False
    # 只掃描白名單中的第一層目錄
    if ROOT == p: return True
    try:
        rel1 = p.relative_to(ROOT).parts[0]
    except Exception:
        return False
    return rel1 in WHITELIST

scanned = changed_files = 0
for path in ROOT.rglob("*.py"):
    if not should_scan(path.parent): continue
    # 跳過 hotfix 自己
    if "scripts/hotfix" in str(path).replace("\\","/"): continue
    try:
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
    except Exception:
        continue
    rw = Rewriter()
    new_tree = rw.visit(tree)
    if not rw.changed:
        continue
    scanned += 1
    backup = BACKUP_ROOT / path.relative_to(ROOT)
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup)
    new_code = ast.unparse(new_tree)
    path.write_text(new_code, encoding="utf-8")
    print(f"[patched] {path}")
    changed_files += 1

print(f"[DONE] scanned={scanned} changed={changed_files} backup_at={BACKUP_ROOT}")
