#!/usr/bin/env bash
# 從 $HOME 起掃大型模型檔，依內容雜湊去重：每組只保留一份，其餘搬到隔離夾（可還原）
set -Eeuo pipefail
shopt -s nullglob

TS="$(date +%Y%m%d_%H%M%S)"
HOME_ROOT="${HOME}"
ROOTS=(${ROOTS:-"$HOME_ROOT"})      # 可以空白分隔多個路徑，但預設只掃 $HOME
MIN_MB="${MIN_MB:-100}"             # 只處理 >=100MB
EXTS="${EXTS:-safetensors,safetensors.*,bin,bin.*,pt,ckpt,ckpt.*,onnx,pb,pth,pth.tar,tflite,weights,params}"
# keeper 目錄優先序（由高到低）；會優先保留這些目錄中的檔
KEEP_DIRS="${KEEP_DIRS:-$HOME/projects/smart-mail-agent_ssot/artifacts_kie,$HOME/projects/smart-mail-agent_ssot/artifacts,$HOME/projects,$HOME}"
KEEP="${KEEP:-}"                    # 指定必留單一檔（可空）
DRY_RUN="${DRY_RUN:-0}"             # 1=只列出動作不搬移
DO_SUDO="${DO_SUDO:-0}"             # 1=對無權限檔案 sudo -n 搬移（無密碼快取則記錄失敗）

WORK="${WORK:-/var/tmp/sma_home_scan_$TS}"
OUT="${OUT:-$PWD/reports_auto/quarantine_home_$TS}"
LOG="$OUT/quarantine_log.csv"
TODO="$OUT/move_todo.txt"
HASHLIST="$WORK/hashlist.csv"
SORTED="$WORK/hashlist.sorted.csv"

mkdir -p "$WORK" "$OUT"
echo 'action,fullpath,bytes,hash,keeper,ts' > "$LOG"
: > "$TODO"

# 排除自身隔離/報告與常見無用目錄（不排除 ~/.cache）
EXCLUDE_DIRS=(
  "$OUT"
  "$PWD/reports_auto/quarantine_home_"
  "$PWD/reports_auto/quarantine_root_"
  "$PWD/reports_auto/quarantine_models_"
  "$PWD/.venv"
  "$HOME/.local/share/Trash"
)
is_excluded_dir(){
  local p="$1"
  for d in "${EXCLUDE_DIRS[@]}"; do
    [[ "$p" == "$d"* ]] && return 0
  done
  return 1
}

# 1) 串流列舉 -> 計算 SHA256 -> 寫入 hashlist.csv（hash,size,mtime,path）
echo "[1/3] 掃描 $HOME_ROOT 並計算雜湊 -> $HASHLIST"
python3 - "$MIN_MB" "$HASHLIST" "${ROOTS[@]}" <<'PY'
import os, sys, hashlib
MIN_MB = int(sys.argv[1]); HASHLIST = sys.argv[2]; ROOTS = sys.argv[3:]
MIN_BYTES = MIN_MB*1024*1024
# 目標副檔名族群
pats_ext = ('safetensors','bin','pt','ckpt','onnx','pb','pth','tflite','weights','params')
# 也納入像 *.pth.tar、*.ckpt.*、*.safetensors.*、*.bin.*
extra_ends = ('pth.tar',)
extra_subs = ('safetensors.','ckpt.','bin.')

def want(path:str)->bool:
    name = os.path.basename(path).lower()
    if any(name.endswith('.'+p) for p in pats_ext): return True
    if any(name.endswith(p) for p in extra_ends): return True
    if any(s in name for s in extra_subs): return True
    return False

def sha256(path, buf=1024*1024):
    h = hashlib.sha256()
    with open(path,'rb') as f:
        while True:
            b = f.read(buf)
            if not b: break
            h.update(b)
    return h.hexdigest()

with open(HASHLIST,'w',encoding='utf-8') as out:
    for root in ROOTS:
        for dp, dn, fn in os.walk(root):
            # 排除一些無謂的巨量目錄（不排除 .cache）
            base = os.path.basename(dp)
            if base in {'.git','node_modules','__pycache__','.ruff_cache','.pytest_cache','.mypy_cache'}:
                dn[:] = []  # stop descending
                continue
            for n in fn:
                p = os.path.join(dp,n)
                try:
                    sz = os.path.getsize(p)
                    if sz < MIN_BYTES: continue
                    if not want(p): continue
                    h = sha256(p)
                    mt = int(os.path.getmtime(p))
                    out.write(f"{h},{sz},{mt},{p}\n")
                except Exception:
                    continue
PY

# 2) 依 hash 排序（讓相同內容相鄰） -> 省記憶體
echo "[2/3] 排序 hash 分組 -> $SORTED"
sort -t, -k1,1 "$HASHLIST" -o "$SORTED"

# 3) 串流分組 -> 選 keeper -> 搬移重複檔到隔離夾
echo "[3/3] 去重並搬移到隔離夾：$OUT"
python3 - "$SORTED" "$LOG" "$OUT" "$KEEP" "$KEEP_DIRS" "$DRY_RUN" "$DO_SUDO" "$TODO" <<'PY'
import os, sys, time, shutil, subprocess
SORTED, LOG, OUT, KEEP, KEEP_DIRS, DRY_RUN, DO_SUDO, TODO = sys.argv[1:]
prior_dirs = [d for d in KEEP_DIRS.split(',') if d]
DRY_RUN = (DRY_RUN == '1'); DO_SUDO = (DO_SUDO == '1')
now = time.strftime('%Y-%m-%dT%H:%M:%S')

def in_dir(p, d):
    try: return os.path.commonpath([os.path.abspath(p), os.path.abspath(d)]) == os.path.abspath(d)
    except: return False

def can_touch(path):
    # 避免觸碰隔離夾自身
    return not os.path.abspath(path).startswith(os.path.abspath(OUT))

def move(p, dest):
    if DRY_RUN: return True, ""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        shutil.move(p, dest); return True, ""
    except Exception as e:
        if DO_SUDO:
            try:
                subprocess.check_call(['sudo','-n','mkdir','-p',os.path.dirname(dest)])
                subprocess.check_call(['sudo','-n','mv','-f',p,dest])
                return True, ""
            except Exception as ee:
                return False, str(ee)
        return False, str(e)

with open(SORTED,'r',encoding='utf-8') as f, \
     open(LOG,'a',encoding='utf-8') as lg, \
     open(TODO,'a',encoding='utf-8') as todo:
    cur_h, rows = None, []
    def process_group(h, rows):
        if not rows: return 0
        # rows: list of "h,sz,mt,path"
        paths = [r.split(',',3)[3].rstrip('\n') for r in rows]
        sizes = [int(r.split(',',3)[1]) for r in rows]
        # 選 keeper：先 KEEP 命中，其次依 prior_dirs，其次路徑短者
        keeper = None
        if KEEP and KEEP in paths: keeper = KEEP
        if keeper is None:
            for d in prior_dirs:
                for p in paths:
                    if in_dir(p, d): keeper = p; break
                if keeper: break
        if keeper is None:
            keeper = min(paths, key=lambda s: (len(s), s))
        lg.write(f'keep,"{keeper}",0,{h},"{keeper}","{now}"\n')
        saved = 0
        for (p, sz) in zip(paths, sizes):
            if p == keeper or not can_touch(p): 
                continue
            rel = os.path.relpath(p, '/').replace('\\','/')
            dest = os.path.join(OUT, rel)
            ok, err = move(p, dest)
            if ok:
                lg.write(f'move,"{p}",{sz},{h},"{keeper}","{now}"\n')
                saved += sz
            else:
                lg.write(f'error,"{p}",{sz},{h},"{err}","{now}"\n')
                todo.write(p + "\n")
        return saved
    total = 0
    for line in f:
        h = line.split(',',1)[0]
        if h != cur_h and cur_h is not None:
            total += process_group(cur_h, rows); rows=[]
        cur_h = h; rows.append(line)
    if rows: total += process_group(cur_h, rows)
    print(total)
PY

# 產出摘要
MOVED_BYTES=$(awk -F, '$1=="move"{s+=$3}END{print s+0}' "$LOG" 2>/dev/null || echo 0)
echo "== 完成 =="
awk -v b="${MOVED_BYTES:-0}" 'BEGIN{printf "搬移總量(估): %.2f GB\n", b/1073741824}'
echo "隔離夾: $OUT"
echo "紀錄 CSV: $LOG"
[[ -s "$TODO" ]] && echo "無權限/占用待處理清單: $TODO"
/mnt/c/Windows/explorer.exe "$(wslpath -w "$OUT")" >/dev/null 2>&1 || true
