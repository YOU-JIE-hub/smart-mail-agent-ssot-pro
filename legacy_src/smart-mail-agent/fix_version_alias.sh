#!/usr/bin/env bash
set -Eeuo pipefail

# 1) 寫死版本字串模組（覆寫）
cat > src/smart_mail_agent/__version__.py <<'PY'
__all__ = ["__version__"]
__version__ = "0.4.0"
PY

# 2) 套件入口只 re-export 字串（覆寫）
cat > src/smart_mail_agent/__init__.py <<'PY'
from __future__ import annotations
from .__version__ import __version__
__all__ = ["__version__"]
PY

# 3) 驗證
python - <<'PY'
import smart_mail_agent as s
import smart_mail_agent.cli.sma as cli
print("pkg file:", s.__file__)
print("pkg version:", s.__version__)
print("cli file:", cli.__file__)
PY

echo "—— 使用 -S（不載入 sitecustomize）再次檢查 ——"
python -S -m smart_mail_agent.cli.sma --version
