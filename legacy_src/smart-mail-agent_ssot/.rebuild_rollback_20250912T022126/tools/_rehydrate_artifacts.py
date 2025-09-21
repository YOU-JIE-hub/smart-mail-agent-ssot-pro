from __future__ import annotations
import os, json, shutil, hashlib, sys, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AP = ROOT / "artifacts_prod"
REQ = [
    "model_pipeline.pkl",
    "ens_thresholds.json",
    "intent_rules_calib_v11c.json",
    "intent_contract.json",
    "kie_runtime_config.json",
]

def to_wsl_path(p: str) -> str:
    if not p: return p
    s = p.replace("\\", "/")
    # //wsl.localhost/Ubuntu-22.04/home/youjie/... → /home/youjie/...
    m = re.match(r"^/{1,2}wsl\.localhost/[^/]+/(.+)$", s, flags=re.I)
    if m: return "/" + m.group(1).lstrip("/")
    # \\wsl.localhost\Ubuntu-22.04\home\youjie\... → /home/youjie/...
    m = re.match(r"^\\\\wsl\.localhost\\[^\\]+\\(.+)$", p, flags=re.I)
    if m: return "/" + m.group(1).replace("\\","/").lstrip("/")
    # file:///home/... → /home/...
    if s.lower().startswith("file:///"): return s[7:]
    return s

def sha256_of(path: Path) -> str:
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""): h.update(chunk)
    return h.hexdigest()[:12]

def parse_pointer(txt: str) -> dict:
    # 支援 JSON 指示、單行路徑、含關鍵字 path/link/target、或 "POINTER: <path> sha=... size=..."
    t = txt.strip()
    # JSON?
    try:
        obj = json.loads(t)
        if isinstance(obj, dict):
            for k in ("path","link","target","real_path"):
                if k in obj and obj[k]: return {"path": str(obj[k]), "sha": obj.get("sha256"), "size": obj.get("size")}
    except Exception:
        pass
    # KEY=VALUE 聚合？
    m = re.search(r"path\s*=\s*(\S+)", t, flags=re.I)
    if m: return {"path": m.group(1)}
    # POINTER: /abs/path sha=... size=...
    m = re.search(r"(?:POINTER|REAL|FILE)[:=]\s*(\S+)", t, flags=re.I)
    if m: return {"path": m.group(1)}
    # 單行即路徑
    if "\n" not in t and len(t) > 1 and (t.startswith("/") or t.startswith("\\") or t.startswith(".")):
        return {"path": t}
    return {}

def rehydrate_one(name: str) -> tuple[bool,str]:
    dst = AP / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    # 夠大就視為已實體
    try:
        if dst.exists() and dst.stat().st_size > 4096:
            return True, f"[SKIP] {name} already real ({dst.stat().st_size} bytes, sha={sha256_of(dst)})"
    except FileNotFoundError:
        pass

    # 讀指示檔
    if not dst.exists():
        return False, f"[MISS] indicator missing: {dst}"
    try:
        raw = dst.read_bytes()
    except Exception as e:
        return False, f"[ERR] read {dst}: {e!r}"

    ptr = parse_pointer(raw.decode("utf-8", errors="ignore"))
    cand = to_wsl_path(ptr.get("path","")).strip()
    # 若指示檔內沒有 path，試幾個常見位置（同名 .real、同目錄 sibling）
    guesses = []
    if cand: guesses.append(cand)
    guesses += [
        str(dst)+".real",
        str(dst).replace(".json",".real.json"),
        str(ROOT/ name),  # 同名直指（萬一被搬過）
    ]
    # 去重
    seen=set(); candidates=[]
    for g in guesses:
        g = g.strip()
        if not g or g in seen: continue
        seen.add(g); candidates.append(g)

    src = None
    for g in candidates:
        p = Path(g)
        if p.is_file() and p.stat().st_size > 4096:
            src = p; break

    if not src:
        return False, f"[MISS] real file not found for {name}; candidates={candidates}"

    # 複製覆蓋（避免 symlink 權限問題）
    try:
        shutil.copy2(src, dst)
        return True, f"[OK] {name} <- {src} ({dst.stat().st_size} bytes, sha={sha256_of(dst)})"
    except Exception as e:
        return False, f"[ERR] copy {src} -> {dst}: {e!r}"

def main():
    results=[]
    for n in REQ:
        ok,msg = rehydrate_one(n)
        print(msg)
        results.append(ok)
    # KIE 目錄（若在 config 內有 weights_dir）
    try:
        cfg = json.load(open(AP/"kie_runtime_config.json", encoding="utf-8"))
        wdir = to_wsl_path(str(cfg.get("weights_dir","")).strip())
        if wdir and os.path.isdir(wdir):
            dst = AP/"kie"
            if not dst.exists():
                shutil.copytree(wdir, dst)
                print(f"[OK] KIE tree <- {wdir}")
            else:
                print(f"[SKIP] KIE tree already exists: {dst}")
    except Exception:
        pass

    if not all(results):
        missing=[REQ[i] for i,ok in enumerate(results) if not ok]
        print(f"[FATAL] rehydrate incomplete; missing={missing}", file=sys.stderr)
        sys.exit(3)

if __name__=="__main__":
    main()
