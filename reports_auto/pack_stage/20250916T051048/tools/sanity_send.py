#!/usr/bin/env python3
import os, smtplib, time
from email.message import EmailMessage

def send_test(to_addr: str):
    user = os.getenv("SMA_SMTP_USER") or os.getenv("SMTP_USER")
    pw   = os.getenv("SMA_SMTP_PASS") or os.getenv("SMTP_PASS")
    host = os.getenv("SMA_SMTP_HOST","smtp.gmail.com")
    port = int(os.getenv("SMA_SMTP_PORT","587"))
    tls  = os.getenv("SMA_SMTP_TLS","starttls")

    if not user or not pw:
        raise RuntimeError("缺少 SMTP 帳密（SMA_SMTP_USER/SMA_SMTP_PASS 或 SMTP_USER/SMTP_PASS）")

    msg = EmailMessage()
    msg["Subject"] = "【Sanity Test】UTF-8 內容與附件測試 ✓"
    msg["From"] = user
    msg["To"] = to_addr

    # 內文：純文字 + HTML（自動 UTF-8）
    plain = "這是一封編碼驗證信：中文/Emoji 😃 OK\n時間: " + time.strftime("%Y-%m-%d %H:%M:%S")
    html  = """<!doctype html><meta charset="utf-8">
    <h1>HTML 內文：中文/Emoji 😃 OK</h1>
    <p>這是驗證信，用來檢查 UTF-8 與附件是否正常。</p>"""
    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")

    # 附件（關鍵修正點）：
    # 文字型附件：只給 subtype=...（用「關鍵字參數」）；不要傳 maintype/charset
    msg.add_attachment("附件TXT：中文行、emoji 😃、第二行", subtype="plain", filename="示範_UTF8.txt")
    msg.add_attachment("<!doctype html><meta charset='utf-8'><h2>附件HTML：中文OK 😃</h2>",
                       subtype="html", filename="demo.html")
    msg.add_attachment("姓名,分數\n小明,90\n小美,85\n", subtype="csv", filename="data.csv")

    # 二進位附件：用位置參數指定 ('image','png')
    png_bytes = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                 b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDATx\x9cc``\x00"
                 b"\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82")
    msg.add_attachment(png_bytes, "image", "png", filename="dot.png")

    srv = smtplib.SMTP(host, port, timeout=20)
    srv.ehlo()
    if tls.lower() == "starttls":
        import ssl
        srv.starttls(context=ssl.create_default_context())
        srv.ehlo()
    srv.login(user, pw)
    srv.send_message(msg)
    srv.quit()
    print("[OK] sanity test mail sent to", to_addr)

if __name__ == "__main__":
    to = os.getenv("RECIPIENT") or os.getenv("SANITY_TO") or "h125872359@gmail.com"
    send_test(to)
