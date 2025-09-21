#!/usr/bin/env python3
# 檔案位置：src/inference_classifier.py
# 模組用途：繁體郵件意圖分類與內容摘要推論（支援本地訓練模型與中文 summarizer）
import argparse
import json
import os

import torch
from dotenv import load_dotenv
from transformers import (
    AutoModelForSeq2SeqLM,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    pipeline,
)

from smart_mail_agent.utils.logger import logger

load_dotenv()

# 預設模型設定
DEFAULT_CLASSIFIER_PATH = os.getenv("CLASSIFIER_PATH", "model/roberta-zh-checkpoint")
DEFAULT_SUMMARIZER = os.getenv("SUMMARIZER_MODEL", "uer/pegasus-base-chinese-cluecorpussmall")


def load_model(model_path: str):
    """載入意圖分類模型（分類器）"""
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"找不到分類模型路徑：{model_path}")
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(model_path, local_files_only=True)

    if not hasattr(model.config, "id2label") or not isinstance(model.config.id2label, dict):
        logger.warning("模型缺少 id2label，預設為 0~N")
        model.config.id2label = {i: str(i) for i in range(model.config.num_labels)}
        model.config.label2id = {v: k for k, v in model.config.id2label.items()}

    return tokenizer, model


def load_summarizer(name: str = DEFAULT_SUMMARIZER):
    """載入摘要模型（Summarizer）"""
    try:
        tokenizer = AutoTokenizer.from_pretrained(name)
        model = AutoModelForSeq2SeqLM.from_pretrained(name)
        return pipeline("summarization", model=model, tokenizer=tokenizer)
    except Exception as e:
        logger.warning(f"[Summarizer] 載入失敗：{e}")
        return None


def smart_truncate(text: str, max_chars: int = 1000) -> str:
    """智慧截斷長文本，避免超過模型長度限制"""
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.4)]
    mid_start = int(len(text) / 2 - max_chars * 0.15)
    mid_end = int(len(text) / 2 + max_chars * 0.15)
    middle = text[mid_start:mid_end]
    tail = text[-int(max_chars * 0.3) :]
    return head + "\n...\n" + middle + "\n...\n" + tail


def classify(text: str, tokenizer, model) -> tuple:
    """執行分類推論，回傳 (label, confidence)"""
    text = smart_truncate(text)
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=512)
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        probs = torch.nn.functional.softmax(logits, dim=1)[0]
        confidence, pred_idx = torch.max(probs, dim=0)
        label = model.config.id2label.get(pred_idx.item(), "unknown")
        return label, float(confidence)


def summarize(text: str, summarizer) -> str:
    """使用摘要模型產生總結內容"""
    try:
        result = summarizer(text, max_length=48, min_length=8, do_sample=False)
        return result[0]["summary_text"]
    except Exception as e:
        logger.warning(f"[Summarize] 摘要失敗：{e}")
        return ""


def classify_intent(subject: str, content: str) -> dict:
    """
    給定主旨與內文，執行意圖分類推論

    回傳:
        {
            "label": 分類標籤,
            "confidence": 預測信心值 (0~1)
        }
    """
    try:
        text = f"{subject.strip()}\n{content.strip()}"
        tokenizer, model = load_model(DEFAULT_CLASSIFIER_PATH)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model.to(device)
        label, confidence = classify(text, tokenizer, model)
        return {"label": label, "confidence": round(confidence, 4)}
    except Exception as e:
        logger.error(f"[IntentClassifier] 推論失敗：{e}")
        return {"label": "unknown", "confidence": 0.0}


def main():
    parser = argparse.ArgumentParser(description="繁體郵件分類與摘要工具")
    parser.add_argument("--input", required=True, help="輸入 JSON 信件檔案")
    parser.add_argument("--output", required=True, help="輸出分類結果 JSON 檔案")
    args = parser.parse_args()

    input_path = args.input
    output_path = args.output

    if not os.path.exists(input_path):
        logger.error(f"[Input] 找不到輸入檔案：{input_path}")
        return

    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    subject = data.get("subject", "").strip()
    content = data.get("content", "").strip()
    text = f"{subject}\n{content}"

    try:
        tokenizer, model = load_model(DEFAULT_CLASSIFIER_PATH)
        model.to("cuda" if torch.cuda.is_available() else "cpu")
        label, score = classify(text, tokenizer, model)
    except Exception as e:
        logger.error(f"[Classifier] 分類錯誤：{e}")
        label, score = "unknown", 0.0

    try:
        summarizer = load_summarizer()
        summary = summarize(text, summarizer) if summarizer else ""
    except Exception as e:
        logger.warning(f"[Summarizer] 摘要跳過：{e}")
        summary = ""

    result = {
        "subject": subject,
        "content": content,
        "label": label,
        "confidence": round(score, 4),
        "summary": summary,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info(f"[Output] 分類完成：{label}（信心值：{score:.4f}） ➜ {output_path}")


if __name__ == "__main__":
    main()
