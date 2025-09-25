import imaplib
import os
import re

from dotenv import load_dotenv

from smart_mail_agent.utils.logger import logger

load_dotenv()
#!/usr/bin/env python3
# 檔案位置：src/utils/imap_utils.py
# 模組用途：偵測 Gmail 的 All Mail 資料夾名稱，支援不同語系與 IMAP 編碼


def _decode_imap_bytes(v: bytes | tuple[bytes, ...] | bytearray) -> str:
    """統一處理 IMAP 回傳：可能為 bytes 或 (bytes, ...)。
    盡力解碼，失敗則回傳 str(v)。"""
    try:
        if isinstance(v, (bytes, bytearray)):
            return _decode_imap_bytes(v)
        if isinstance(v, tuple) and v:
            # 常見格式 (b'OK', [b'INBOX']) / (b'...', b'...')
            first = v[0]
            if isinstance(first, (bytes, bytearray)):
                return _decode_imap_bytes(first)
        return str(v)
    except Exception:
        return str(v)


def detect_all_mail_folder() -> str:
    """
    自動偵測 Gmail 中的 All Mail 資料夾名稱，支援中英文、UTF7 編碼格式。

    若找不到，預設回傳 'INBOX' 作為 fallback。

    回傳:
        str: Gmail 中的 All Mail 資料夾名稱（或 INBOX）
    """
    imap_host = os.getenv("IMAP_HOST")
    imap_user = os.getenv("IMAP_USER")
    imap_pass = os.getenv("IMAP_PASS")

    if not imap_host or not imap_user or not imap_pass:
        logger.warning("[IMAP] 無法建立連線，環境變數缺漏，使用預設 INBOX")
        return "INBOX"

    try:
        with imaplib.IMAP4_SSL(imap_host) as imap:
            imap.login(imap_user, imap_pass)
            status, mailboxes = imap.list()
            if status != "OK":
                logger.warning("[IMAP] 無法列出 Gmail 資料夾，使用預設 INBOX")
                return "INBOX"

            for line in mailboxes:
                parts = _decode_imap_bytes(line).split(' "/" ')
                if len(parts) != 2:
                    continue
                _, name = parts
                if re.search(r"All Mail|所有郵件|&UWiQ6JD1TvY-", name, re.IGNORECASE):
                    folder = name.strip().strip('"')
                    logger.info(f"[IMAP] 偵測到 All Mail 資料夾：{folder}")
                    return folder

            logger.warning("[IMAP] 找不到 All Mail，使用預設 INBOX")
            return "INBOX"

    except Exception as e:
        logger.warning(f"[IMAP] 連線失敗（fallback INBOX）：{e}")
        return "INBOX"
