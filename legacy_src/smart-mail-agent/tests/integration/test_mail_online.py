import os
from pathlib import Path
import pytest

from ai_rpa import mail_io

need_smtp = all([
    os.getenv("SMA_SMTP_HOST"),
    os.getenv("SMA_SMTP_PORT"),
    os.getenv("SMA_SMTP_USER"),
    os.getenv("SMA_SMTP_PASS"),
    os.getenv("SMA_SMTP_TO"),
])
need_imap = all([
    os.getenv("SMA_IMAP_HOST"),
    os.getenv("SMA_IMAP_USER"),
    os.getenv("SMA_IMAP_PASS"),
])

@pytest.mark.skipif(os.getenv("OFFLINE") == "1" or not need_smtp, reason="SMTP env not set or OFFLINE=1")
def test_smtp_send_online(tmp_path, monkeypatch):
    monkeypatch.setenv("OFFLINE", "0")  # 允許外呼
    outbox = tmp_path/"outbox"; outbox.mkdir()
    ret = mail_io.send_email(
        outbox=outbox,
        to_addr=os.environ["SMA_SMTP_TO"],
        subject="SMA Integration SMTP",
        body="hello from integration test",
        attachments=None,
        dry_run=False,
        db_log=None,
    )
    # 線上模式：預期真的打 SMTP
    assert ret["ok"] is True and ret["via"] == "smtp"
    assert Path(ret["path"]).exists()

@pytest.mark.skipif(os.getenv("OFFLINE") == "1" or not need_imap, reason="IMAP env not set or OFFLINE=1")
def test_imap_receive_online(monkeypatch):
    monkeypatch.setenv("OFFLINE", "0")  # 允許外呼
    msgs = mail_io.receive_imap(
        host=os.environ["SMA_IMAP_HOST"],
        user=os.environ["SMA_IMAP_USER"],
        password=os.environ["SMA_IMAP_PASS"],
        folder=os.getenv("SMA_IMAP_FOLDER", "INBOX"),
        limit=int(os.getenv("SMA_IMAP_LIMIT", "5")),
        timeout=10,
    )
    # 信箱可能是空的，至少確認能連通、且格式正確
    assert isinstance(msgs, list)
