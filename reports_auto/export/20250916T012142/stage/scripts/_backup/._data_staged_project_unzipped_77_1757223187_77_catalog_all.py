from __future__ import annotations
import os, re, sys, json, ast, hashlib, datetime as dt, sqlite3, traceback
from pathlib import Path
from typing import Dict, List, Tuple, Any

ROOT = Path.cwd()
OUT  = ROOT / "reports_auto/_catalog"
LOG  = ROOT / "reports_auto/logs/pipeline.ndjson"
DB   = ROOT / "db/sma.sqlite"
OUT.mkdir(parents=True, exist_ok=True)

# ---------- utils ----------
def now_iso()->str: return dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
def sha256_bytes(b:bytes)->str: import hashlib; return hashlib.sha256(b).hexdigest()
def sha256_path(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""): h.update(chunk)
    return h.hexdigest()

def log_ndjson(payload:Dict[str,Any]):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts":now_iso(), **payload}, ensure_ascii=False)+"\n")

def log_error(stage:str, mail_id:str, message:str, tb:str):
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS err_log(ts, mail_id, stage, message, traceback)")
    con.execute("INSERT INTO err_log VALUES (?,?,?,?,?)",
                (now_iso(), mail_id, stage, message, tb))
    con.commit(); con.close()

# ---------- scan ----------
EXCLUDE = {".git",".venv",".vscode",".cache","__pycache__","node_modules","dist","out","tmp","build","Archive","archive"}
def want_dir(rel:Path)->bool:
    parts = set(str(p) for p in rel.parts)
    return not (parts & EXCLUDE)

TEXT_EXT = {".py",".sh",".ini",".toml",".cfg",".md",".txt",".json",".yaml",".yml",".sql",".csv"}
def is_text_file(p:Path)->bool: return p.suffix.lower() in TEXT_EXT

GROUP_RULES: List[Tuple[re.Pattern,str]] = [
    (re.compile(r"(^|/)tests(_smoke)?(/|$)"), "tests"),
    (re.compile(r"(^|/)ai_rpa(/|$)"), "old_ai_rpa"),
    (re.compile(r"(^|/)smart_mail_agent(/|$)"), "old_sma"),
    (re.compile(r"(^|/)sma(/|$)"), "new_sma"),
    (re.compile(r"(^|/)reports(_auto)?(/|$)"), "reports"),
]
def classify(path:Path)->str:
    s = path.as_posix()
    for pat, tag in GROUP_RULES:
        if pat.search(s): return tag
    return "other"

def module_guess(p:Path)->str|None:
    if p.suffix!=".py": return None
    rel = p.relative_to(ROOT).as_posix()
    if any(rel.split("/",1)[0]==x for x in ("ai_rpa","smart_mail_agent","sma")):
        return rel[:-3].replace("/", ".")
    return None

# ---------- parse Python for symbols & imports ----------
def parse_python(p:Path)->Dict[str,Any]:
    out: Dict[str,Any] = {"defs":[], "classes":[], "imports":[], "errors":None}
    try:
        src = p.read_text(encoding="utf-8", errors="ignore")
        t = ast.parse(src, filename=str(p))
        for n in t.body:
            if isinstance(n, ast.FunctionDef):
                args = [a.arg for a in n.args.args]
                out["defs"].append({"name": n.name, "args": args, "lineno": n.lineno})
            elif isinstance(n, ast.ClassDef):
                out["classes"].append({"name": n.name, "lineno": n.lineno})
            elif isinstance(n, ast.Import):
                for a in n.names: out["imports"].append(a.name)
            elif isinstance(n, ast.ImportFrom):
                mod = n.module or ""
                out["imports"].append(mod)
    except Exception as e:
        out["errors"] = f"{type(e).__name__}: {e}"
    return out

# ---------- walk ----------
files: List[Path] = []
for dp, dns, fns in os.walk(ROOT):
    rel = Path(dp).relative_to(ROOT)
    if not want_dir(rel): continue
    for fn in fns:
        p = Path(dp) / fn
        if p.is_file() and is_text_file(p):
            files.append(p)

# ---------- build indexes ----------
index_path  = OUT / "index.jsonl"
symbols_path= OUT / "symbols.jsonl"
imports_graph_path = OUT / "import_graph.json"
missing_modules_path = OUT / "missing_modules.json"
conflicts_path = OUT / "conflicts.json"
codebook_prefix = OUT / "ALL_CODE_part_"

dup_hash: Dict[str, List[str]] = {}
imports_edges: List[Tuple[str,str]] = []
all_imports: List[str] = []
missing_modules: Dict[str, List[str]] = {}
name_collisions: Dict[str, List[str]] = {}

# map of module string -> file existence
module_to_file: Dict[str, str] = {}

# prime module map for ai_rpa/smart_mail_agent/sma trees
for p in files:
    if p.suffix==".py":
        mg = module_guess(p)
        if mg: module_to_file[mg] = str(p.relative_to(ROOT))

# write index/symbols, compute graphs
index_path.unlink(missing=True)
symbols_path.unlink(missing=True)

with index_path.open("a", encoding="utf-8") as idx, symbols_path.open("a", encoding="utf-8") as sym:
    for p in sorted(files):
        try:
            b = p.read_bytes()
        except Exception as e:
            # skip unreadable
            continue
        sha = sha256_bytes(b)
        dup_hash.setdefault(sha, []).append(str(p.relative_to(ROOT)))
        grp = classify(p)
        mg  = module_guess(p)
        rec = {
            "path": str(p.relative_to(ROOT)),
            "size": len(b),
            "sha256": sha,
            "mtime": dt.datetime.utcfromtimestamp(p.stat().st_mtime).isoformat()+"Z",
            "group": grp,
            "module_guess": mg,
            "ext": p.suffix.lower(),
        }
        idx.write(json.dumps(rec, ensure_ascii=False)+"\n")

        if p.suffix==".py":
            info = parse_python(p)
            sym.write(json.dumps({"path": rec["path"], **info}, ensure_ascii=False)+"\n")
            # imports graph
            src_mod = mg or rec["path"]
            for imp in info["imports"]:
                if not imp: continue
                imports_edges.append((src_mod, imp))
                all_imports.append(imp)

# missing modules (only ai_rpa/smart_mail_agent/sma prefixed)
def is_target(m:str)->bool:
    return m and (m=="ai_rpa" or m=="smart_mail_agent" or m=="sma" or m.startswith(("ai_rpa.","smart_mail_agent.","sma.")))

missing = {}
for m in sorted({i for i in all_imports if is_target(i)}):
    # seen module but no file recorded
    if m not in module_to_file and not any(k.startswith(m+".") for k in module_to_file):
        missing[m] = True

with missing_modules_path.open("w", encoding="utf-8") as f:
    json.dump({"missing": sorted(missing.keys())}, f, ensure_ascii=False, indent=2)

# name collisions (top-level defs/classes with same name in different files)
sym_index: Dict[str, List[str]] = {}
try:
    import itertools, json
    for line in symbols_path.read_text(encoding="utf-8").splitlines():
        obj = json.loads(line)
        path = obj["path"]
        for d in obj.get("defs", []):
            key = f"def::{d['name']}"
            sym_index.setdefault(key, []).append(path)
        for c in obj.get("classes", []):
            key = f"class::{c['name']}"
            sym_index.setdefault(key, []).append(path)
    name_collisions = {k:v for k,v in sym_index.items() if len(set(v))>1}
except Exception:
    name_collisions = {}

# imports graph json
nodes = sorted({a for a,_ in imports_edges} | {b for _,b in imports_edges})
edges = [{"from":a,"to":b} for a,b in imports_edges]
with imports_graph_path.open("w", encoding="utf-8") as f:
    json.dump({"nodes":nodes, "edges":edges}, f, ensure_ascii=False, indent=2)

with conflicts_path.open("w", encoding="utf-8") as f:
    json.dump({
        "duplicate_files_by_hash": {h:paths for h,paths in dup_hash.items() if len(paths)>1},
        "name_collisions": name_collisions
    }, f, ensure_ascii=False, indent=2)

# new-tree plan (read-only mapping proposal)
def plan_target(mod:str|None, path:str)->str:
    # 單一新架構 sma/…
    if not mod or not (mod.startswith("ai_rpa") or mod.startswith("smart_mail_agent")):
        return f"sma/legacy/{path}"
    # 粗略切到子域（離線規則，之後可再調整）
    parts = mod.split(".")
    top = parts[1] if len(parts)>1 else "legacy"
    mapping = {
        "actions_router":"actions", "actions_executor":"actions",
        "mailguard":"spam", "spam_adapter":"spam",
        "file_classifier":"files",
        "mail_io":"mail",
        "ocr":"ocr",
        "nlp":"nlp", "nlp_llm":"nlp",
        "observability":"observability",
        "core":"core", "sma_core":"core",
        "utils":"utils", "types":"types",
        "main":"cli",
    }
    sub = mapping.get(top, "legacy")
    leaf = parts[-1]
    return f"sma/{sub}/{leaf}.py"

plan_path = OUT / "new_tree_plan.jsonl"
with plan_path.open("w", encoding="utf-8") as f:
    for p in files:
        mg = module_guess(p) if p.suffix==".py" else None
        tgt = plan_target(mg, str(p.relative_to(ROOT)))
        f.write(json.dumps({
            "from": str(p.relative_to(ROOT)),
            "module_guess": mg,
            "to": tgt
        }, ensure_ascii=False)+"\n")

# codebook (split parts)
MAX_PART_BYTES = 2_000_000  # ~2MB/part，避免超大檔
part_idx, buf = 1, []
cur = 0
def flush():
    global part_idx, buf, cur
    if not buf: return
    out = OUT / f"ALL_CODE_part_{part_idx:04d}.md"
    out.write_text("".join(buf), encoding="utf-8")
    buf, cur = [], 0
    part_idx += 1

for p in sorted(files):
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    header = f"\n\n# FILE: {p.relative_to(ROOT)}\n\n" \
             f"- size: {len(txt.encode('utf-8','ignore'))} bytes\n" \
             f"- sha256: {sha256_path(p)}\n" \
             f"- group: {classify(p)}\n" \
             f"- module_guess: {module_guess(p)}\n\n"
    block = header + "```" + (p.suffix[1:] if len(p.suffix)>1 else "") + "\n" + txt + "\n```\n"
    b = block.encode("utf-8","ignore")
    if cur + len(b) > MAX_PART_BYTES:
        flush()
    buf.append(block); cur += len(b)
flush()

# human summary
summary_md = OUT / "REFactor_PLAN.md"
conf = json.loads(conflicts_path.read_text(encoding="utf-8"))
miss = json.loads(missing_modules_path.read_text(encoding="utf-8"))
with summary_md.open("w", encoding="utf-8") as f:
    f.write("# Refactor Read-Only Plan (Catalog)\n\n")
    f.write("- 代碼全集導出：ALL_CODE_part_*.md\n")
    f.write("- index：index.jsonl；symbols：symbols.jsonl；匯入圖：import_graph.json\n")
    f.write("- 缺模組：missing_modules.json；衝突：conflicts.json\n")
    f.write("- 新樹規劃：new_tree_plan.jsonl（僅規劃，不改檔）\n\n")
    f.write("## 缺模組（僅靜態分析）\n")
    for m in miss.get("missing", [])[:100]:
        f.write(f"- {m}\n")
    if len(miss.get("missing", []))>100:
        f.write(f"... ({len(miss['missing'])-100} more)\n")
    f.write("\n## 可能的名稱衝突（同名 def/class 出現在多處）\n")
    for k,paths in list(conf.get("name_collisions",{}).items())[:50]:
        f.write(f"- {k} -> {len(set(paths))} files\n")
    if len(conf.get("name_collisions",{}))>50:
        f.write(f"... ({len(conf['name_collisions'])-50} more)\n")

log_ndjson({"stage":"catalog","message":"completed"})
print(json.dumps({"ok":True,"out_dir":str(OUT)}, ensure_ascii=False))
