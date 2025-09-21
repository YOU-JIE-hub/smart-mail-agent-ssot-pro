#!/usr/bin/env python3
# 檔案位置：src/send_with_attachment.py
# 模組用途：寄送 Email（支援 HTML 內文、附件、錯誤處理、環境參數與 log 紀錄）
import argparse
import os
import smtplib
import traceback
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
from reportlab.pdfgen import canvas

from smart_mail_agent.utils.logger import logger

# 強制指定 .env 位置
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

# === SMTP 設定參數（需於 .env 中設定）===
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_FROM = os.getenv("SMTP_FROM", f"Smart-Mail-Agent <{SMTP_USER}>")
REPLY_TO = os.getenv("REPLY_TO", SMTP_USER)


# === 驗證 SMTP 參數 ===
def validate_smtp_config():
    missing = []
    for key in ["SMTP_USER", "SMTP_PASS", "SMTP_HOST", "SMTP_PORT"]:
        if not os.getenv(key):
            missing.append(key)
    if missing:
        raise ValueError(f"[SMTP] 設定錯誤，缺少欄位：{', '.join(missing)}")


# === 自動產 PDF（若不存在）===
def generate_sample_pdf(filepath: str):
    try:
        c = canvas.Canvas(filepath)
        c.drawString(100, 750, "這是一封測試郵件的附件 PDF")
        c.save()
        logger.info("[SMTP] 已產生測試 PDF：%s", filepath)
    except Exception as e:
        logger.error("[SMTP] PDF 建立失敗：%s", e)


# === 主寄信函式 ===
def send_email_with_attachment(
    recipient: str,
    subject: str,
    body_html: str = None,
    body_text: str = None,
    attachment_path: str = None,
) -> bool:
    try:
        validate_smtp_config()
    except Exception as e:
        logger.error("[SMTP] 設定錯誤：%s", e)
        return False

    msg = MIMEMultipart()
    msg["From"] = SMTP_FROM
    msg["To"] = recipient
    msg["Subject"] = subject or "(No Subject)"
    msg["Reply-To"] = REPLY_TO

    if body_text:
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    if attachment_path:
        if not os.path.exists(attachment_path) and "sample.pdf" in attachment_path:
            generate_sample_pdf(attachment_path)
        if os.path.exists(attachment_path):
            try:
                with open(attachment_path, "rb") as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
                    part["Content-Disposition"] = (
                        f'attachment; filename="{os.path.basename(attachment_path)}"'
                    )
                    msg.attach(part)
                logger.debug("[SMTP] 附件已加入：%s", attachment_path)
            except Exception as e:
                logger.warning("[SMTP] 附件載入失敗：%s", e)
        else:
            logger.error("[SMTP] 找不到附件：%s", attachment_path)
            return False

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        logger.info("[SMTP] 信件已寄出：%s → %s", subject, recipient)
        return True

    except Exception as e:
        logger.error("[SMTP] 寄信失敗：%s", e)
        logger.debug(traceback.format_exc())
        return False


# === CLI 執行介面 ===
def main():
    parser = argparse.ArgumentParser(description="寄送 Email，支援 HTML 內文與附件")
    parser.add_argument("--to", required=True, help="收件者 Email")
    parser.add_argument("--subject", required=True, help="郵件主旨")
    parser.add_argument("--body", required=True, help="HTML 內文")
    parser.add_argument("--file", required=True, help="附件檔案路徑")

    args = parser.parse_args()

    result = send_email_with_attachment(
        recipient=args.to, subject=args.subject, body_html=args.body, attachment_path=args.file
    )

    if result:
        print("郵件已成功寄出")
    else:
        print("郵件寄出失敗")


if __name__ == "__main__":
    main()
