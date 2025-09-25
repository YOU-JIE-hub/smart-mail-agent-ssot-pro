#!/usr/bin/env bash
# 只保留每個「內容雜湊」的一份大型模型檔；其餘搬到隔離夾（可還原）
set -Eeuo pipefail
ROOT="${ROOT:-$(pwd)}"
TS="$(date +%Y%m%d_%H%M%S)"
Q="$ROOT/reports_auto/quarantine_large_models_$TS"
LOG="$Q/quarantine_log.csv"
MIN_MB="${MIN_MB:-50}"   # 只處理 >= 50MB（可調）
# 目標副檔名（大小寫不敏感；含 safetensors.*、ckpt.*）
EXTS="${EXTS:-safetensors,safetensors.*,bin,pt,ckpt,ckpt.*,onnx,pb,pth,tflite,weights,params}"
# 指定要保留的單一檔（可選，僅當內容雜湊相符才會命中）
KEEP="${KEEP:-}"
# 優先保留的目錄（逗號分隔；依序匹配）
KEEP_DIRS="${KEEP_DIRS:-$ROOT/artifacts_kie,$ROOT/artifacts,$ROOT/models,$ROOT/outputs}"

mkdir -p "$Q"
echo 'action,fullpath,bytes,hash,keeper,ts' > "$LOG"

MOVED_BYTES="$(
python3 - "$ROOT" "$Q" "$LOG" "$MIN_MB" "$EXTS" "$KEEP" "$KEEP_DIRS" <<'PY'
import os, sys, time, hashlib, shutil

ROOT, Q, LOG, MIN_MB, EXTS, KEEP, KEEP_DIRS = sys.argv[1:]
MIN_BYTES = int(float(MIN_MB)) * 1024 * 1024
ext_patterns = [e.strip().lower() for e in EXTS.split(',') if e.strip()]
priority_dirs = [d for d in KEEP_DIRS.split(',') if d]

def want(path:str)->bool:
    name = os.path.basename(path).lower()
    for pat in ext_patterns:
        if pat.endswith('.*'):
            base = pat[:-2]
            if name.startswith(base + '.'): return True
        else:
            if name.endswith('.'+pat) or name == pat: return True
    return False

def excluded_dir(d:str)->bool:
    parts = set(d.split(os.sep))
    bad = {'.git','node_modules','.venv','__pycache__','.ruff_cache','.pytest_cache','.mypy_cache','build','dist','.cache'}
    return len(parts & bad) > 0

def sha256(path, buf=1024*1024):
    h = hashlib.sha256()
    with open(path,'rb') as f:
        while True:
            b = f.read(buf)
            if not b: break
            h.update(b)
    return h.hexdigest()

# 收集候選
candidates=[]
for dp, dn, fn in os.walk(ROOT):
    if excluded_dir(dp): continue
    for n in fn:
        p = os.path.join(dp,n)
        try:
            if os.path.getsize(p) < MIN_BYTES: continue
        except Exception:
            continue
        if want(p): candidates.append(p)

# 依內容雜湊分組
groups={}
for p in candidates:
    try:
        h = sha256(p)
    except Exception:
        continue
    groups.setdefault(h, []).append(p)

# 選 keeper 並搬移重複者
moved_bytes = 0
now = time.strftime('%Y-%m-%dT%H:%M:%S')
def in_dir(p, d):
    try:
        return os.path.commonpath([os.path.abspath(p), os.path.abspath(d)]) == os.path.abspath(d)
    except Exception:
        return False

# 若提供 KEEP，先計算其雜湊（避免重複計算）
keep_hash = None
if KEEP and os.path.exists(KEEP):
    try: keep_hash = sha256(KEEP)
    except Exception: keep_hash = None

with open(LOG,'a',encoding='utf-8') as lg:
    for h, paths in groups.items():
        # 決定 keeper
        keeper = None
        if keep_hash == h:
            keeper = KEEP
        if keeper is None:
            for d in priority_dirs:
                for p in paths:
                    if in_dir(p, d):
                        keeper = p; break
                if keeper: break
        if keeper is None:
            keeper = min(paths, key=lambda s: (len(s), s))  # 路徑短者優先

        lg.write(f'keep,"{keeper}",0,{h},"{keeper}","{now}"\n')

        for p in paths:
            if p == keeper: continue
            try: sz = os.path.getsize(p)
            except Exception: sz = 0
            rel = os.path.relpath(p, ROOT)
            dest = os.path.join(Q, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            try:
                shutil.move(p, dest)
                moved_bytes += sz
                lg.write(f'move,"{p}",{sz},{h},"{keeper}","{now}"\n')
            except Exception as e:
                lg.write(f'error,"{p}",{sz},{h},"{str(e)}","{now}"\n')

print(moved_bytes)
PY
)"

# 摘要輸出
echo "== 完成 =="
awk -v b="${MOVED_BYTES:-0}" 'BEGIN{printf "搬移總量: %.2f GB\n", b/1073741824}'
echo "隔離夾: $Q"
echo "紀錄檔: $LOG"
/mnt/c/Windows/explorer.exe "$(wslpath -w "$Q")" >/dev/null 2>&1 || true
