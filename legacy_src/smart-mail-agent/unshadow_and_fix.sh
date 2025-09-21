#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "❌ 失敗於第 $LINENO 行（exit=$?）" >&2' ERR

ts="$(date +%Y%m%d%H%M%S)"

# 0) venv
if [ ! -x ".venv/bin/python" ]; then python3 -m venv .venv; fi
. .venv/bin/activate
python -m pip -q install -U pip wheel >/dev/null

# 1) 移開會「搶路徑」的目錄（只在存在時移動）
if [ -d smart_mail_agent ] && [ ! -L smart_mail_agent ]; then
  mv smart_mail_agent ".z_legacy_smart_mail_agent_${ts}"
  echo "↪ 已移開 ./smart_mail_agent → .z_legacy_smart_mail_agent_${ts}"
fi
for d in .release_stage .backup_conflicts_*; do
  [ -e "$d" ] || continue
  mv "$d" ".z_legacy_${d//\//_}_${ts}"
  echo "↪ 已移開 $d → .z_legacy_${d//\//_}_${ts}"
done

# 2) 建立 src 骨架（可重複執行）
mkdir -p src/smart_mail_agent/cli src/smart_mail_agent/core/utils src/smart_mail_agent/utils tests

# 3) 版本檔（若缺才建）
if [ ! -f src/smart_mail_agent/__init__.py ]; then
  cat > src/smart_mail_agent/__init__.py <<'PY'
from __future__ import annotations
__all__ = ["__version__"]
__version__ = "0.4.0"
PY
  echo "✓ 寫入 src/smart_mail_agent/__init__.py"
fi

# 4) CLI（覆寫）
cat > src/smart_mail_agent/cli/sma.py <<'PY'
from __future__ import annotations
import argparse
from .. import __version__

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sma", description="Smart Mail Agent CLI")
    p.add_argument("--version", action="store_true", help="顯示版本")
    ns = p.parse_args(argv)
    if ns.version:
        print(__version__)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
PY
echo "✓ 寫入 src/smart_mail_agent/cli/sma.py"

# 5) 最小 PDF 工具 + re-export（覆寫，純 Python，無外網依賴）
cat > src/smart_mail_agent/core/utils/pdf_safe.py <<'PY'
from __future__ import annotations
from pathlib import Path

def _escape_pdf_text(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

def _write_minimal_pdf(out_path: str | Path, text: str) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = _escape_pdf_text(text or "")
    content = (
        "%PDF-1.1\n1 0 obj<<>>endobj\n2 0 obj<<>>endobj\n"
        "3 0 obj<</Length 44>>stream\n"
        f"BT /F1 12 Tf 72 720 Td ({payload}) Tj ET\n"
        "endstream endobj\n4 0 obj<</Type/Page/Parent 2 0 R/Contents 3 0 R>>endobj\n"
        "5 0 obj<</Type/Pages/Count 1/Kids[4 0 R]>>endobj\n"
        "6 0 obj<</Type/Catalog/Pages 5 0 R>>endobj\nxref\n0 7\n0000000000 65535 f \n"
        "trailer<</Root 6 0 R/Size 7>>\nstartxref\n351\n%%EOF\n"
    )
    p.write_bytes(content.encode("latin-1", errors="ignore"))
    return str(p)

def write_pdf_or_txt(out_path: str | Path, text: str) -> str:
    try:
        return _write_minimal_pdf(out_path, text)
    except Exception:
        p = Path(out_path).with_suffix(".txt")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(text or ""), encoding="utf-8")
        return str(p)
PY

cat > src/smart_mail_agent/utils/pdf_safe.py <<'PY'
from __future__ import annotations
from smart_mail_agent.core.utils.pdf_safe import *  # re-export
PY
echo "✓ 寫入 pdf_safe（core + re-export）"

# 6) 最小 pyproject（無外部依賴，離線可裝）
cat > pyproject.toml <<'TOML'
[build-system]
requires = ["setuptools>=65", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "smart-mail-agent"
version = "0.4.0"
requires-python = ">=3.10"
description = "AI/RPA Smart Mail Agent (minimal skeleton)"
readme = "README.md"
license = {text = "MIT"}
authors = [{ name = "You-Jie Song" }]

[tool.setuptools.packages.find]
where = ["src"]
include = ["smart_mail_agent*"]
TOML
echo "✓ 寫入 pyproject.toml"

# 7) 乾淨可編輯安裝 + 清理快取
find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
pip -q uninstall -y smart-mail-agent >/dev/null 2>&1 || true
pip -q install -e . >/dev/null
echo "✓ pip install -e . 完成"

# 8) 驗證「實際載入路徑」與版本（含 -S 避開 sitecustomize）
python - <<'PY'
import inspect
import smart_mail_agent.cli.sma as s
print("Loaded from:", s.__file__)
print("Version (module):", getattr(s, "__version__", "?"))
import smart_mail_agent as pkg
print("Version (package):", getattr(pkg, "__version__", "?"))
PY

echo "—— 使用 -S（不載入 sitecustomize）再次檢查 ——"
python -S -m smart_mail_agent.cli.sma --version
