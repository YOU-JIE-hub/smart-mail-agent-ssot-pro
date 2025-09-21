from __future__ import annotations

import imaplib
import os

from dotenv import load_dotenv


def get_imap():
    load_dotenv(dotenv_path=".env", override=True)
    host = os.getenv("IMAP_HOST", "imap.gmail.com").strip()
    user = os.getenv("IMAP_USER", "").strip()
    pwd = os.getenv("IMAP_PASS", "").strip()

    if not user or not pwd:
        raise RuntimeError(f"IMAP_USER/IMAP_PASS 缺失（user={bool(user)}, pass_len={len(pwd)})")

    # 開啟 debug 方便看到 LOGIN 是否為兩個參數
    imaplib.Debug = int(os.getenv("IMAP_DEBUG", "0"))
    imap = imaplib.IMAP4_SSL(host, 993)
    imap.login(user, pwd)  # 這裡一定是兩個參數
    return imap
