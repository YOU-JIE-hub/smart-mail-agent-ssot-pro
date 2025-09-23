#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace; umask 022
cd ~/projects/smart-mail-agent-ssot-pro || exit 2
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"

TS="$(date +%Y%m%dT%H%M%S)"
PROOT="reports_auto/pro/pro_${TS}"; mkdir -p "$PROOT"

# 2.1 若有你原本的專業評測腳本就跑，沒有就忽略
[ -f scripts/eval_pro.py ]      && python scripts/eval_pro.py      || true
[ -f scripts/build_pro_md.py ]  && python scripts/build_pro_md.py  || true

# 2.2 latest 指向最近一組 pro_*
python - <<'PY'
from pathlib import Path; import shutil
root=Path("reports_auto/pro")
dirs=sorted([p for p in root.glob("pro_*") if p.is_dir()], key=lambda p:p.name, reverse=True)
if dirs:
    latest=root/"latest"
    try:
        if latest.exists() or latest.is_symlink(): latest.unlink()
        latest.symlink_to(dirs[0].name)
    except Exception:
        if latest.exists(): shutil.rmtree(latest, ignore_errors=True)
        shutil.copytree(dirs[0], latest, dirs_exist_ok=True)
print("[OK] pro latest ->", dirs[0] if dirs else "NA")
PY

# 2.3 做 Spam 校準（輸出到 latest）
python scripts/calibrate_spam.py --out reports_auto/pro/latest

# 2.4 打包證據
zip -qr "reports_auto/bundles/pro_evidence_${TS}.zip" reports_auto/pro/latest || true
echo "[OK] Pro+Calib bundle -> reports_auto/bundles/pro_evidence_${TS}.zip"
