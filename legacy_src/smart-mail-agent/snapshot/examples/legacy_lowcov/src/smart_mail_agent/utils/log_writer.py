from __future__ import annotations

#!/usr/bin/env python3
# 檔案位置：src/utils/log_writer.py
# 模組用途：向後相容封裝（統一轉用 src.log_writer.log_to_db）
from smart_mail_agent.log_writer import log_to_db  # re-export

__all__ = ["log_to_db"]
