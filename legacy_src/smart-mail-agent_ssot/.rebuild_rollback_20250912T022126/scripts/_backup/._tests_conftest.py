#!/usr/bin/env python3
# 檔案位置: tests/conftest.py
# 模組用途: 在測試收集階段把 src/ 注入 sys.path，並設 SMA_ROOT/OFFLINE 預設。
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
os.environ.setdefault("SMA_ROOT", str(ROOT))
os.environ.setdefault("OFFLINE", os.environ.get("OFFLINE", "1"))
