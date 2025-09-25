#!/usr/bin/env bash
set -Eeuo pipefail

# —— 0) venv —— #
if [ ! -x ".venv/bin/python" ]; then python3 -m venv .venv; fi
. .venv/bin/activate
python -m pip -q install -U pip wheel

# —— 1) 最小可運作套件骨架（多次執行安全） —— #
mkdir -p src/smart_mail_agent/cli src/smart_mail_agent/core/utils src/smart_mail_agent/utils tests

# __init__.py（若不存在才建立）
if [ ! -f src/smart_mail_agent/__init__.py ]; then
  cat > src/smart_mail_agent/__init__.py <<'PY'
from __future__ import annotations
__all__ = ["__version__"]
__version__ = "0.4.0"
PY
fi

# CLI 入口（覆寫以修復上次中斷）
cat > src/smart_mail_agent/cli/sma.py <<'PY'
from __future__ import annotations
import argparse

__version__ = "0.4.0"

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

# 安全 PDF 工具（核心實作）
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
        "%PDF-1.1\n"
        "1 0 obj<<>>endobj\n"
        "2 0 obj<<>>endobj\n"
        "3 0 obj<</Length 44>>stream\n"
        f"BT /F1 12 Tf 72 720 Td ({payload}) Tj ET\n"
        "endstream endobj\n"
        "4 0 obj<</Type/Page/Parent 2 0 R/Contents 3 0 R>>endobj\n"
        "5 0 obj<</Type/Pages/Count 1/Kids[4 0 R]>>endobj\n"
        "6 0 obj<</Type/Catalog/Pages 5 0 R>>endobj\n"
        "xref\n0 7\n0000000000 65535 f \n"
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

# 對外 re-export（相容舊引用路徑）
cat > src/smart_mail_agent/utils/pdf_safe.py <<'PY'
from __future__ import annotations
from smart_mail_agent.core.utils.pdf_safe import *  # re-export
PY

# pyproject（簡化設定；先確保可安裝與執行）
cat > pyproject.toml <<'TOML'
[build-system]
requires = ["setuptools>=65", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "smart-mail-agent"
version = "0.4.0"
requires-python = ">=3.10"
description = "AI/RPA Smart Mail Agent"
readme = "README.md"
license = {text = "MIT"}
authors = [{ name = "You-Jie Song" }]
dependencies = [
  "jinja2>=3.1,<4",
  "python-dotenv>=1.0",
  "PyYAML>=6",
  "reportlab>=3.6,<4",
]
[project.optional-dependencies]
dev = ["pytest>=7.4"]

[tool.setuptools.packages.find]
where = ["src"]
include = ["smart_mail_agent*"]

[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]
TOML

# 安裝（可編輯）
pip -q install -e ".[dev]"

# 簡單驗證 CLI
python -m smart_mail_agent.cli.sma --version

echo "✅ 完成。之後可執行：python -m smart_mail_agent.cli.sma --version"
