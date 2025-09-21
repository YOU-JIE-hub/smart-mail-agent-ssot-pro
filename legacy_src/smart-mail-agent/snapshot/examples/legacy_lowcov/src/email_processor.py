#!/usr/bin/env python3
# 檔案位置：src/email_processor.py
# 模組用途：主流程入口，整合垃圾信過濾 → 意圖分類 → 執行對應行動模組
import argparse
import json
import os

from dotenv import load_dotenv

from action_handler import route_action
from inference_classifier import classify_intent
from smart_mail_agent.utils.log_writer import write_log
from smart_mail_agent.utils.logger import logger
from spam.spam_filter_orchestrator import SpamFilterOrchestrator

load_dotenv()


def extract_fields(data: dict) -> tuple:
    """
    從 JSON 結構中抽取主旨、內容、寄件人欄位，並標準化欄位名稱

    :param data: dict 輸入信件資料
    :return: tuple(subject, body, sender)
    """
    subject = data.get("subject", "") or data.get("title", "")
    body = data.get("content", "") or data.get("body", "")
    sender = data.get("sender", "") or data.get("from", "")
    return subject.strip(), body.strip(), sender.strip()


def write_classification_result(data: dict, path: str) -> None:
    """
    將分類結果寫回原始 JSON 檔案

    :param data: dict 欲寫入內容
    :param path: str 檔案路徑
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="處理單一信件 JSON，進行 spam 過濾與意圖分類")
    parser.add_argument("--input", required=True, help="輸入 JSON 信件檔案路徑")
    args = parser.parse_args()
    input_path = args.input

    if not os.path.exists(input_path):
        logger.error(f"[Pipeline] 找不到輸入檔案：{input_path}")
        return

    try:
        with open(input_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"[Pipeline] 無法讀取 JSON：{e}")
        return

    subject, body, sender = extract_fields(data)
    logger.info(f"[Pipeline] 處理信件：{subject} / 寄件人：{sender}")

    try:
        spam_filter = SpamFilterOrchestrator()
        result = spam_filter.is_legit(subject, body, sender)

        if not result["allow"]:
            logger.warning(
                f"[Spam] 被過濾：階段 {result.get('stage') or result.get('engine', 'blocked')}"
            )
            data.update(
                {"label": "spam", "predicted_label": "spam", "confidence": 0.0, "summary": ""}
            )
            write_classification_result(data, input_path)
            write_log(
                subject,
                body,
                sender,
                "Spam",
                result.get("stage") or result.get("engine", "blocked"),
                confidence=0.0,
            )
            return

        classification = classify_intent(subject, body)
        label = classification.get("label", "其他")
        confidence = classification.get("confidence", 0.0)

        try:
            confidence_val = float(confidence)
        except Exception:
            confidence_val = 0.0
            logger.warning(f"[Classifier] 信心值轉換失敗：{confidence}")

        logger.info(f"[Classifier] 分類為：{label}（信心值：{confidence_val:.4f}）")

        data.update(
            {"label": label, "predicted_label": label, "confidence": round(confidence_val, 4)}
        )
        write_classification_result(data, input_path)

        try:
            route_action(
                label,
                {
                    "subject": subject,
                    "body": body,
                    "sender": sender,
                    "summary": data.get("summary", ""),
                    "predicted_label": label,
                    "confidence": confidence_val,
                },
            )
            logger.info(f"[Action] 任務執行完成：{label}")
            write_log(subject, body, sender, label, "success", confidence=confidence_val)
        except Exception as action_err:
            logger.error(f"[Action] 任務執行失敗：{action_err}")
            write_log(
                subject,
                body,
                sender,
                label,
                f"action_error: {action_err}",
                confidence=confidence_val,
            )

    except Exception as e:
        logger.error(f"[Pipeline] 處理流程發生例外錯誤：{e}")
        write_log(subject, body, sender, "Error", f"exception: {str(e)}", confidence=0.0)


if __name__ == "__main__":
    main()
