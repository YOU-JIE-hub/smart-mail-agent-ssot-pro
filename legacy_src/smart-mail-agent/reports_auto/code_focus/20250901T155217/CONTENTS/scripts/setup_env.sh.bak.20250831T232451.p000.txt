#!/usr/bin/env bash
set -Eeuo pipefail
python -m venv .venv 2>/dev/null || true
. .venv/bin/activate
python -m pip -q install -U pip
if [[ -f requirements.txt ]]; then
  pip -q install -r requirements.txt
else
  pip -q install pytest pytest-cov PyYAML requests beautifulsoup4 Pillow
fi
PYLIB="$(python - <<'PY'
import sysconfig; print(sysconfig.get_paths()['purelib'])
PY
)"
echo "$PWD/src" > "$PYLIB/smart_mail_agent_src.pth"
echo "已寫入 $PYLIB/smart_mail_agent_src.pth -> $PWD/src"
echo "環境完成。使用：. .venv/bin/activate"
