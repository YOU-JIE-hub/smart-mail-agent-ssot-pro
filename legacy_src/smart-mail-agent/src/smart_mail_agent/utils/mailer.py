import os

REQUIRED = ["SMTP_USER", "SMTP_PASS", "SMTP_HOST", "SMTP_PORT"]


def validate_smtp_config() -> dict:
    missing = [k for k in REQUIRED if not os.getenv(k)]
    if missing:
        raise ValueError(f"SMTP 設定錯誤: 缺少 {', '.join(missing)}")
    return {k: os.getenv(k) for k in REQUIRED}
