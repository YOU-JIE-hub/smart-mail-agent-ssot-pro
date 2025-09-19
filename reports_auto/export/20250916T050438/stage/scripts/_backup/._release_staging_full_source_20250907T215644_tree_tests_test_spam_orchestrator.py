#!/usr/bin/env python3
# 檔案位置: tests/test_spam_orchestrator.py
# 模組用途: 驗證 spam orchestrator 對明顯垃圾樣本為 True。
from smart_mail_agent.spam.spam_filter_orchestrator import is_spam


def test_obvious_spam_true() -> None:
    txt = "限時優惠 比特幣 USDT 點此 https://x.y"
    assert is_spam(txt, sender="noreply@scam.biz", threshold=0.6) is True
