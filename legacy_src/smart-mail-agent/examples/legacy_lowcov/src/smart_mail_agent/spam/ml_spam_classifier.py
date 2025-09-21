#!/usr/bin/env python3
# mypy: ignore-errors
# 檔案位置：src/spam/ml_spam_classifier.py
# 模組用途：使用 fine-tuned BERT 模型進行垃圾郵件分類預測

import torch
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    TextClassificationPipeline,
)

from smart_mail_agent.utils.logger import logger


def smart_truncate(text: str, max_chars: int = 1000) -> str:
    """
    對長文本進行三段式裁切：保留前段、中段、尾段內容，確保語意不中斷。

    :param text: 原始文本
    :param max_chars: 限制總長度
    :return: 裁切後文本
    """
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.4)]
    mid_start = int(len(text) / 2 - max_chars * 0.15)
    mid_end = int(len(text) / 2 + max_chars * 0.15)
    middle = text[mid_start:mid_end]
    tail = text[-int(max_chars * 0.3) :]
    return head + "\n...\n" + middle + "\n...\n" + tail


class SpamBertClassifier:
    """
    使用 HuggingFace Transformers 微調模型進行 spam/ham 分類
    """

    def __init__(self, model_path: str):
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"[SpamBertClassifier] 載入 BERT 模型：{model_path}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_path).to(device)
        self.pipeline = TextClassificationPipeline(
            model=self.model,
            tokenizer=self.tokenizer,
            device=0 if device.type == "cuda" else -1,
            top_k=None,
        )

    def predict(self, subject: str, content: str) -> dict:
        """
        執行垃圾信預測分類

        :param subject: 信件主旨
        :param content: 信件內容
        :return: dict 包含 label 與 confidence
        """
        text = smart_truncate(f"{subject.strip()}\n{content.strip()}", max_chars=1000)

        try:
            preds = self.pipeline(text)[0]
            preds = sorted(preds, key=lambda x: x["score"], reverse=True)
            pred_label = preds[0]["label"]
            confidence = round(preds[0]["score"], 4)
            logger.debug(f"[SpamBertClassifier] 預測結果：{pred_label} (信心值：{confidence})")
            return {"label": pred_label, "confidence": confidence}
        except Exception as e:
            logger.error(f"[SpamBertClassifier] 預測失敗：{str(e)}")
            return {"label": "unknown", "confidence": 0.0}
