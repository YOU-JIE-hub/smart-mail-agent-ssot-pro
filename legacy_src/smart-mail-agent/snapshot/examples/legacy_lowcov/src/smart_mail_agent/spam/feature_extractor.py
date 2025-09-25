#!/usr/bin/env python3
# 檔案位置：src/spam/feature_extractor.py
# 模組用途：從原始 Email 字串中擷取關鍵特徵，用於垃圾郵件判斷（供 ML 模型使用）

import re
from email import message_from_string


def extract_features(raw_email: str) -> dict[str, int]:
    """
    從原始 Email 內文中抽取特徵向量，用於垃圾郵件偵測模型。

    參數:
        raw_email (str): 原始 email 字串（含標頭與主體）

    回傳:
        dict: 包含以下欄位的特徵向量：
            - subject_len (int): 主旨長度
            - num_urls (int): URL 出現次數
            - has_attachment (int): 是否含非純文字附件（1/0）
            - num_recipients (int): 收件人數量（To + Cc）
    """
    msg = message_from_string(raw_email)

    subject = msg.get("Subject", "") or ""
    to_list = msg.get_all("To", []) or []
    cc_list = msg.get_all("Cc", []) or []

    features = {
        "subject_len": len(subject),
        "num_urls": len(re.findall(r"https?://", raw_email)),
        "has_attachment": int(msg.get_content_maintype() not in ["text", "multipart"]),
        "num_recipients": len(to_list + cc_list),
    }

    return features
