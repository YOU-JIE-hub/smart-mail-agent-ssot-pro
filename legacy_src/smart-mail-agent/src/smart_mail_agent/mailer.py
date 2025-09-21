from __future__ import annotations

import os


def validate_smtp_config():
    need = ["SMTP_USER", "SMTP_PASS", "SMTP_HOST", "SMTP_PORT"]
    missing = [k for k in need if not os.environ.get(k)]
    if missing:
        raise ValueError("SMTP 設定錯誤：缺少 " + ",".join(missing))
    return True
