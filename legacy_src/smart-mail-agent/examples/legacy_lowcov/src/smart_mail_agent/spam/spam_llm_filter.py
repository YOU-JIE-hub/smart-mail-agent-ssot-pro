import os

#!/usr/bin/env python3
# 檔案位置：src/spam/spam_llm_filter.py
# 模組用途：使用 OpenAI GPT 模型判斷信件是否具詐騙/釣魚嫌疑（L2）
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

from smart_mail_agent.utils.logger import logger

load_dotenv()


class SpamLLMFilter:
    """
    使用 OpenAI GPT API 進行詐騙信判斷（L2 分層）
    回傳是否可疑（bool）
    """

    def __init__(self, model: str = "gpt-3.5-turbo", max_tokens: int = 256):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("[SpamLLMFilter] 缺少必要環境變數 OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def is_suspicious(self, subject: str, content: str) -> bool:
        """
        呼叫 OpenAI 判斷是否為詐騙信件。

        :param subject: 信件主旨
        :param content: 信件內容
        :return: bool - 是否具可疑詐騙嫌疑
        """
        try:
            full_text = f"主旨：{subject}\n內容：{content}".strip()
            prompt = f"判斷以下郵件是否為詐騙信或社交工程釣魚信。\n如果你判斷為【正常信件】，請回：OK\n如果你判斷為【可能詐騙或釣魚】，請回：SUSPICIOUS\n\n{full_text}"

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是資安專家，負責分析詐騙信件。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=0.0,
            )

            answer = response.choices[0].message.content.strip().upper()
            logger.debug(f"[SpamLLMFilter] 判斷結果：{answer}")
            return "SUSPICIOUS" in answer

        except OpenAIError as e:
            logger.error(f"[SpamLLMFilter] OpenAI API 錯誤：{e}")
        except Exception as e:
            logger.error(f"[SpamLLMFilter] LLM 判斷失敗：{e}")

        return False  # fallback 預設為非可疑
