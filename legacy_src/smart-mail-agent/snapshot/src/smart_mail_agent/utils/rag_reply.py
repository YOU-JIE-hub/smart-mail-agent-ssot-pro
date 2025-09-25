from __future__ import annotations

import os

#!/usr/bin/env python3
# 檔案位置：src/utils/rag_reply.py
# 模組用途：使用 GPT 模型 + FAQ 知識庫進行回應生成（中文 Retrieval-Augmented Generation）
from dotenv import load_dotenv

try:
    from openai import OpenAI, OpenAIError  # type: ignore

    _OPENAI_AVAILABLE = True
except Exception:
    # ImportError or others

    class OpenAIError(Exception): ...

    class OpenAI:  # minimal stub so module can import
        def __init__(self, *a, **k):
            raise RuntimeError("openai package not available")

    _OPENAI_AVAILABLE = False

from smart_mail_agent.utils.logger import logger

load_dotenv()


def load_faq_knowledge(faq_path: str) -> str:
    """
    讀取 FAQ 知識庫文字內容

    :param faq_path: FAQ 文字檔案路徑
    :return: FAQ 資料字串
    """
    if not os.path.exists(faq_path):
        logger.warning(f"[rag_reply] 找不到 FAQ 檔案：{faq_path}")
        return ""

    try:
        with open(faq_path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"[rag_reply] FAQ 讀取錯誤：{e}")
        return ""


def generate_rag_reply(query: str, faq_path: str, model: str = "gpt-3.5-turbo") -> str:
    """
    根據 FAQ 資料與提問內容產生回覆內容

    :param query: 使用者提出的問題
    :param faq_path: FAQ 資料檔案路徑
    :param model: 使用之 GPT 模型名稱
    :return: 回覆文字
    """
    try:
        faq = load_faq_knowledge(faq_path)
        if not faq:
            return "很抱歉，目前無法提供對應資料。"

        prompt = f"你是客服助理，請根據以下 FAQ 資訊與提問內容，提供簡潔清楚的回覆：\n\n【FAQ】\n{faq}\n\n【提問】\n{query}\n\n請以繁體中文回答，回覆不可重複 FAQ 原文，請使用簡明語氣說明即可。"

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "你是客服 AI 專員，回答使用者關於流程與規則的問題。",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=400,
            temperature=0.7,
        )

        answer = response.choices[0].message.content.strip()
        logger.info("[rag_reply] 回覆產生成功")
        return answer

    except OpenAIError as e:
        logger.error(f"[rag_reply] OpenAI 回應錯誤：{e}")
        return "目前系統繁忙，請稍後再試。"

    except Exception as e:
        logger.error(f"[rag_reply] 回覆產生異常：{e}")
        return "處理過程發生錯誤，請稍後再試。"
