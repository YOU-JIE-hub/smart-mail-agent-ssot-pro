#!/usr/bin/env bash
set -Eeuo pipefail
say(){ echo "[$(date +%H:%M:%S)] $*"; }

# ---- Vars
ROOT="${PROJ:-$HOME/projects/smart-mail-agent_ssot}"
TS="$(date +%Y%m%dT%H%M%S)"
export ROOT TS                              # <— 關鍵：給 Python 拿得到
OUT="$ROOT/handoff/$TS"
LOG="$OUT/handoff_${TS}.log"
mkdir -p "$OUT"
exec > >(tee -a "$LOG") 2>&1

# ---- open folder helper
open_path(){ 
  local p="$1"
  if grep -qi microsoft /proc/version 2>/dev/null && command -v wslpath >/dev/null 2>&1; then
    explorer.exe "$(wslpath -w "$p")" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$p" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then open "$p" >/dev/null 2>&1 || true
  fi
}

# ---- ERR trap：失敗時開資料夾
trap 'code=$?; echo "[ERROR] exit=$code. Logs at: $OUT"; open_path "$OUT"; exit $code' ERR

# 0) 進專案＋啟環境
say "enter project & venv → $ROOT"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"

# 1) 清理/封存
say "cleanup: fold legacy & merge artifacts"
mkdir -p legacy/db legacy/tools reports_auto/status

# 舊 runner 歸檔（存在才動）
[ -f scripts/e2e_mail_runner.py ] && { mv -n scripts/e2e_mail_runner.py legacy/; echo "[MOVE] scripts/e2e_mail_runner.py → legacy/"; } || true

# 雙層 artifacts_prod 收斂
if [ -d artifacts_prod/artifacts_prod ]; then
  shopt -s dotglob nullglob
  mv -n artifacts_prod/artifacts_prod/* artifacts_prod/ || true
  rmdir artifacts_prod/artifacts_prod || true
  shopt -u dotglob nullglob
  echo "[MERGE] artifacts_prod/artifacts_prod/* → artifacts_prod/"
fi

# 舊 DB 封存
for db in data/stats.db db/records.db reports_auto/audit.sqlite3; do
  [ -f "$db" ] && { mv -n "$db" "legacy/db/$(basename "$db")"; echo "[MOVE] $db → legacy/db/"; } || true
done

# 2) 專案審計：工件&最新批次
say "audit: artifacts & latest run"
python - <<'PY'
import os, pathlib, hashlib, time
root = pathlib.Path(os.environ["ROOT"])
ts   = os.environ.get("TS") or time.strftime("%Y%m%dT%H%M%S")
audit= root/"reports_auto"/"status"/f"PROJECT_AUDIT_{ts}.md"
art  = root/"artifacts_prod"
def exist(p): return "FOUND" if p.exists() else "MISSING"
def sha256(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1<<20), b""): h.update(b)
    return h.hexdigest()
lines=[f"# Project Audit ({ts})"]
for name in ("model_pipeline.pkl","ens_thresholds.json","intent_rules_calib_v11c.json","kie_runtime_config.json"):
    p=art/name
    s=f"- {name}: {exist(p)}"
    if p.exists():
        try:
            s+=f" size={p.stat().st_size}"
            if p.suffix in (".pkl",".pt",".bin"): s+=f" sha256={sha256(p)}"
        except Exception: pass
    lines.append(s)
run_root=root/"reports_auto"/"e2e_mail"
try:
    latest=max(run_root.glob("*"), key=lambda p:p.name)
    lines.append(f"- latest run: {latest.name}")
    summ=latest/"SUMMARY.md"
    if summ.exists():
        head="\n".join(summ.read_text(encoding="utf-8", errors="ignore").splitlines()[:30])
        lines.append("```summary\n"+head+"\n```")
except ValueError:
    lines.append("- latest run: (none)")
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text("\n".join(lines), encoding="utf-8")
print(f"[OK] audit written → {audit}")
PY

# 3) 交接包：小檔複製；大檔寫同名 .POINTER
say "export: create trimmed handoff bundle with pointers"
python - <<'PY'
import os, re, csv, glob, shutil, hashlib, pathlib, sys
root=pathlib.Path(os.environ["ROOT"]); ts=os.environ["TS"]
out =root/"handoff"/ts
files_dir=out/"files"; ptr_dir=out/"pointers"
files_dir.mkdir(parents=True, exist_ok=True); ptr_dir.mkdir(parents=True, exist_ok=True)

MAX_SIZE=500*1024  # >500KB 視為大檔
LARGE_RE=[r".*\.pkl$", r".*\.pt$", r".*\.bin$", r"db/sma\.sqlite$", r".*\.eml$"]
INCLUDE_DIRS=["src","tools","scripts","kb","configs"]
INCLUDE_FILES=[".env.example","README.md","requirements.txt","pyproject.toml","setup.cfg","one_click_all_v8.sh"]
EXTRA=["reports_auto/e2e_mail/*/SUMMARY.md","reports_auto/logs/**/*.log","reports_auto/status/PROJECT_AUDIT_*.md"]
manifest=[["path","size","sha256","action","note"]]

def sha256(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1<<20), b""): h.update(b)
    return h.hexdigest()

def is_large(rel,size):
    if size>MAX_SIZE: return True
    s=str(rel).replace("\\","/")
    return any(re.fullmatch(pat, s) for pat in LARGE_RE)

def redact_text(t):
    t=re.sub(r'(SMTP_PASS|SMA_SMTP_PASS|OPENAI_API_KEY)\s*=\s*["\'].+?["\']', r'\1="***REDACTED***"', t)
    t=re.sub(r'(SMTP_PASS|SMA_SMTP_PASS|OPENAI_API_KEY)\s*:\s*.+', r'\1: "***REDACTED***"', t)
    return t

def add(p: pathlib.Path):
    if not p.is_file(): return
    rel=p.relative_to(root); size=p.stat().st_size
    if is_large(rel,size):
        sh=sha256(p) if size < 500*1024*1024 else "-"
        dst=(ptr_dir/rel).with_suffix(p.suffix+".POINTER"); dst.parent.mkdir(parents=True, exist_ok=True)
        note="large or sensitive"
        dst.write_text(
            f"# POINTER (not included)\noriginal_path: {rel}\nsize: {size}\nsha256: {sh}\n"
            "instructions: keep same relative path; restore from original storage before running.\n",
            encoding="utf-8"
        )
        manifest.append([str(rel), str(size), sh, "pointer", note])
    else:
        dst=files_dir/rel; dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            text=p.read_text(encoding="utf-8"); text=redact_text(text); dst.write_text(text, encoding="utf-8")
        except Exception:
            shutil.copy2(p,dst)
        manifest.append([str(rel), str(size), sha256(p), "copy", ""])

# collect
for d in INCLUDE_DIRS:
    base=root/d
    if base.exists():
        for p in base.rglob("*"): add(p)
for f in INCLUDE_FILES:
    p=root/f
    if p.exists(): add(p)
for pat in EXTRA:
    for s in glob.glob(str(root/pat), recursive=True):
        add(pathlib.Path(s))

# manifest & zip
man=out/"MANIFEST.csv"; man.parent.mkdir(parents=True, exist_ok=True)
with open(man,"w",newline="",encoding="utf-8") as w: csv.writer(w).writerows(manifest)
zip_path=out.with_suffix(".zip")
shutil.make_archive(str(out), "zip", out)
print(f"[OK] manifest → {man}")
print(f"[OK] handoff zip → {zip_path}")
PY

# 4) 完成 → 開資料夾
open_path "$OUT"
say "HANDOFF READY → $OUT  (zip: ${OUT}.zip)"
