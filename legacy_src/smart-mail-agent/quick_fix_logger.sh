#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "❌ 失敗於第 $LINENO 行（exit=$?）" >&2' ERR

# 1) 真正的 logger 模組：同時輸出 get_logger 與 module-level logger
cat > src/smart_mail_agent/utils/logger.py <<'PY'
from __future__ import annotations
import logging, sys

def get_logger(name: str = "smart_mail_agent"):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        h = logging.StreamHandler(sys.stdout)
        fmt = logging.Formatter("[%(levelname)s] %(message)s")
        h.setFormatter(fmt)
        logger.addHandler(h)
    return logger

# 供舊碼直接 `from ... import logger`
logger = get_logger()

__all__ = ["get_logger", "logger"]
PY

# 2) 舊路徑相容：core/utils/logger.py 也要能 import 到 logger
cat > src/smart_mail_agent/core/utils/logger.py <<'PY'
from __future__ import annotations
from smart_mail_agent.utils.logger import get_logger, logger
__all__ = ["get_logger", "logger"]
PY

# 3) 另一個歷史相容路徑：utils/logger.py
mkdir -p utils
cat > utils/logger.py <<'PY'
from __future__ import annotations
from smart_mail_agent.utils.logger import get_logger, logger
__all__ = ["get_logger", "logger"]
PY

# 4) 清除快取
find . -type d -name "__pycache__" -prune -exec rm -rf {} + || true
find . -type f -name "*.pyc" -delete || true

echo "✅ 已補上 logger 單例與相容匯入路徑。"
