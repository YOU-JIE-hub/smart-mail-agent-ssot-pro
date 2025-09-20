import os, re, json, hashlib, sys, argparse
from pathlib import Path
from datetime import datetime

# ---------- 參數 ----------
ap = argparse.ArgumentParser()
ap.add_argument("--outdir", required=True)
ap.add_argument("--roots", nargs="+", required=True)
ap.add_argument("--progress", type=int, default=5000)
args = ap.parse_args()

OUT = Path(args.outdir); OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT/"run.log"; ERR = OUT/"run.err"

def log(s): LOG.open("a", encoding="utf-8").write(s.rstrip()+"\n")
def elog(s): ERR.open("a", encoding="utf-8").write(s.rstrip()+"\n")

log(f"[START] {datetime.now().isoformat()} outdir={OUT}")

# ---------- 掃描設定 ----------
dataset_exts = {".jsonl",".ndjson",".json",".csv",".tsv",".parquet",".yaml",".yml",".txt"}
model_exts   = {".pkl",".joblib",".safetensors",".pt",".bin",".onnx",".h5",".npz",".npy"}
code_exts    = {".py",".ipynb",".sh",".bash",".env",".mk",".mak"}
special_model_assets = {
    "tokenizer.json","tokenizer_config.json","special_tokens_map.json",
    "sentencepiece.bpe.model","vocab.json","config.json"
}
skip_dirs = {
    ".git",".venv","venv","__pycache__","node_modules",".mypy_cache",
    ".pytest_cache",".cache","dist","build"
}

# 從代碼抓路徑
re_abs_linux  = re.compile(r'["\'](/home/youjie/[^"\']+)["\']')
re_rel_data   = re.compile(r'["\']((?:\./)?(?:data|datasets|models|weights|artifacts(?:_inbox|_prod)?|reports_auto|intent|spam|kie)[^"\']*)["\']')
re_env_assign = re.compile(r'(?m)^\s*(INTENT_PKL|SPAM_PKL|KIE_DIR)\s*=\s*[\'"]?([^\'"\n]+)[\'"]?')
re_pathlike   = re.compile(r'["\'](\/[^"\']+|(?:\.\/)?[^"\']+(?:\.(?:jsonl|ndjson|json|csv|tsv|parquet|pkl|joblib|safetensors|pt|bin|onnx|h5|npz|npy)))["\']')

AUTHORITATIVE = {
  "INTENT_PKL": "/home/youjie/projects/smart-mail-agent-ssot-pro/intent/intent/artifacts/intent_pro_cal.pkl",
  "SPAM_PKL":   "/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/77/77/artifacts_sa/spam_rules_lr.pkl",
  "KIE_DIR":    "/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/kie1/model",
}

# ---------- 小工具 ----------
def sha256_head(p: Path, limit=1024*1024):
    try:
        h=hashlib.sha256()
        with p.open('rb') as f: h.update(f.read(limit))
        return h.hexdigest()
    except Exception as e:
        elog(f"[SHA256] fail {p}: {e}")
        return None

def classify(p: Path):
    n = p.name
    ext = p.suffix.lower()
    if n in special_model_assets or ext in model_exts:
        return "model-asset" if n in special_model_assets and not (ext in model_exts) else "model"
    if ext in dataset_exts: return "dataset"
    if ext in code_exts or n in ("Makefile","GNUmakefile"): return "code"
    return "other"

def walk(root: Path):
    for dp, dns, fns in os.walk(root, followlinks=False):
        # 過濾大目錄
        dns[:] = [d for d in dns if d not in skip_dirs]
        for fn in fns:
            yield Path(dp)/fn

# 嘗試猜 schema（只讀少量）
def guess_schema(p: Path):
    ext = p.suffix.lower()
    sample_txt = ""
    try:
        if ext in (".jsonl",".ndjson"):
            # 取前三行
            with p.open("r", encoding="utf-8", errors="ignore") as f:
                lines = [next(f,"").strip() for _ in range(3)]
            sample_txt = "\n".join([ln for ln in lines if ln])
            keys = set()
            for ln in lines:
                try:
                    import json as _json
                    obj = _json.loads(ln) if ln else {}
                    if isinstance(obj, dict):
                        keys |= set(obj.keys())
                except Exception:
                    pass
            k = {s.lower() for s in keys}
            if {"text","label"} <= k: return "intent", list(keys)
            if {"subject","body","is_spam"} & k and ("is_spam" in k or "spam" in k): return "spam", list(keys)
            if {"fields","ocr","boxes","entities"} & k: return "kie", list(keys)
            return "unknown", list(keys) if keys else []
        elif ext in (".json",".yaml",".yml"):
            # 只取前 64KB
            with p.open("r", encoding="utf-8", errors="ignore") as f:
                sample_txt = f.read(65536)
            low = sample_txt.lower()
            if ("\"text\"" in low and "\"label\"" in low) or ("text:" in low and "label:" in low):
                return "intent", []
            if "is_spam" in low or "spam:" in low:
                return "spam", []
            if "tokenizer.json" in p.name or "config.json" in p.name:
                return "model-meta", []
            return "unknown", []
        elif ext in (".csv",".tsv"):
            with p.open("r", encoding="utf-8", errors="ignore") as f:
                header = f.readline().strip()
            h = [c.strip().lower() for c in re.split(r'[,\t]', header)]
            if {"text","label"} <= set(h): return "intent", h
            if {"subject","body","is_spam"} & set(h): return "spam", h
            return "unknown", h
        else:
            return "unknown", []
    except Exception as e:
        elog(f"[SCHEMA] {p}: {e}")
        return "unknown", []
# ---------- 執行 ----------
roots = [Path(r) for r in args.roots]
for r in roots: log(f"[ROOT] {r} exists={r.exists()}")

files = []
code_refs = {}
n = 0
for root in roots:
    if not root.exists():
        elog(f"[MISS_ROOT] {root}")
        continue
    for p in walk(root):
        n += 1
        if n % args.progress == 0: log(f"[PROGRESS] scanned={n}")
        try:
            kind = classify(p)
            st = p.stat()
            rec = {
                "path": str(p),
                "root": str(root),
                "name": p.name,
                "ext": p.suffix.lower(),
                "kind": kind,
                "size": st.st_size,
                "mtime": st.st_mtime,
            }
            if kind in ("dataset","model","model-asset"):
                rec["sha256_head"] = sha256_head(p)
            if kind == "dataset":
                t, keys = guess_schema(p)
                rec["schema_guess"] = t
                if keys: rec["sample_keys"] = keys
            files.append(rec)

            if kind=="code" and p.suffix.lower() in (".py",".sh",".bash",".env") and st.st_size <= 2*1024*1024:
                try:
                    txt = p.read_text("utf-8", errors="ignore")
                    refs = set()
                    for rgx in (re_abs_linux, re_rel_data, re_env_assign, re_pathlike):
                        for m in rgx.finditer(txt):
                            if rgx is re_env_assign:
                                refs.add(f"{m.group(1)}={m.group(2)}")
                            else:
                                refs.add(m.group(1))
                    if refs:
                        code_refs[str(p)] = sorted(refs)
                except Exception as e:
                    elog(f"[READ_CODE] {p}: {e}")

        except Exception as e:
            elog(f"[STAT] {p}: {e}")

datasets = [r for r in files if r["kind"]=="dataset"]
models   = [r for r in files if r["kind"] in ("model","model-asset")]

# 權威資產檢查
auth = {}
for k,v in AUTHORITATIVE.items():
    p = Path(v)
    auth[k] = {
        "path": v,
        "exists": p.exists(),
        "is_dir": p.is_dir(),
        "size": (p.stat().st_size if (p.exists() and p.is_file()) else None)
    }

# 寫檔
def dump(name, obj):
    (OUT/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), "utf-8")

dump("DATA_CANDIDATES.json", {"count":len(datasets), "items":datasets})
dump("MODEL_CANDIDATES.json", {"count":len(models), "items":models})
dump("CODE_PATH_REFERENCES.json", code_refs)
dump("AUTHORITATIVE_CHECK.json", {"authoritative": auth})

# 嘗試輸出 .env
env_lines = []
for k in ("INTENT_PKL","SPAM_PKL","KIE_DIR"):
    v = AUTHORITATIVE.get(k)
    if v: env_lines.append(f'{k}="{v}"')
# 從代碼引用再補（若出現 INTENT_PKL=xxx 之類）
for f, refs in code_refs.items():
    for s in refs:
        if s.startswith("INTENT_PKL=") or s.startswith("SPAM_PKL=") or s.startswith("KIE_DIR="):
            env_lines.append(s)
if env_lines:
    (OUT/"MODEL_PATHS.auto.env").write_text("\n".join(sorted(set(env_lines)))+"\n", "utf-8")

# 人類可讀摘要
def human(n):
    if n is None: return "-"
    for u in ("B","KB","MB","GB","TB"):
        if n < 1024: return f"{n:.1f}{u}"
        n/=1024
    return f"{n:.1f}PB"

lines = []
lines.append(f"# Discovery summary @ {datetime.now().isoformat(timespec='seconds')}")
lines.append("## Authoritative assets")
for k,v in auth.items():
    ok = "OK " if v["exists"] else "MISS"
    sz = human(v["size"])
    lines.append(f"- {k}: {ok} {v['path']} (size={sz})")
lines.append("")
def top(lst, n=30): return sorted(lst, key=lambda r: (-r["size"], r["path"]))[:n]
lines.append("## Top dataset-like files (by size, top 30)")
for r in top(datasets):
    name = r.get("schema_guess","?")
    lines.append(f"- {human(r['size']):>8}  {r['ext']:<7} {name:<7}  {r['path']}")
lines.append("")
lines.append("## Top model/weight files (by size, top 30)")
for r in top(models):
    lines.append(f"- {human(r['size']):>8}  {r['ext']:<10} {r['kind']:<11} {r['path']}")
lines.append("")
lines.append("## Code → path references (top 20 by count)")
by_refs = sorted(((k,len(v)) for k,v in code_refs.items()), key=lambda kv: -kv[1])[:20]
for k,cnt in by_refs:
    lines.append(f"- {cnt:>3} refs  {k}")
    for s in code_refs[k][:6]:
        lines.append(f"    • {s}")
(OUT/"SUMMARY.txt").write_text("\n".join(lines), "utf-8")

log(f"[DONE] scanned={len(files)} datasets={len(datasets)} models={len(models)}")
print(str(OUT))
