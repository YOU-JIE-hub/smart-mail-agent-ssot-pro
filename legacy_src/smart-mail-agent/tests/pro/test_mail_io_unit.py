import os, time, json
from pathlib import Path
import types
from ai_rpa import mail_io

def _read_eml_text(p: Path) -> str:
    return p.read_text(errors="ignore")

def test_send_email_offline_writes_eml_and_logs(tmp_path, monkeypatch):
    outbox = tmp_path/"outbox"; outbox.mkdir()
    monkeypatch.setenv("OFFLINE", "1")              # 強制離線，不打 SMTP
    # 假附件：一個存在、一個不存在（觸發 fallback 文本附件邏輯）
    ok_file = tmp_path/"ok.bin"; ok_file.write_bytes(b"\x00\x01")
    missing = tmp_path/"missing.bin"
    log_calls = []
    def fake_db_log(sql, params):
        log_calls.append((sql, params))
    ret = mail_io.send_email(
        outbox=outbox,
        to_addr="a@b.com",
        subject="Test Offline",
        body="hello",
        attachments=[ok_file, missing],
        dry_run=False,
        db_log=fake_db_log,
    )
    assert ret["ok"] is True and ret["via"] == "file"
    eml = Path(ret["path"]); assert eml.exists()
    txt = _read_eml_text(eml)
    assert "Subject: Test Offline" in txt and "To: a@b.com" in txt
    # 有寫審計
    assert any("send_email" in (c[1][3] if len(c)>1 else "") for c in log_calls)

def test_send_email_smtp_success_with_starttls(tmp_path, monkeypatch):
    outbox = tmp_path/"outbox"; outbox.mkdir()
    # 走 SMTP 分支：OFFLINE=0 + 提供主機 + STARTTLS 開啟
    monkeypatch.setenv("OFFLINE", "0")
    monkeypatch.setenv("SMA_SMTP_HOST", "smtp.stub")
    monkeypatch.setenv("SMA_SMTP_PORT", "587")
    monkeypatch.setenv("SMA_SMTP_STARTTLS", "1")
    monkeypatch.setenv("SMA_SMTP_USER", "user")
    monkeypatch.setenv("SMA_SMTP_PASS", "pass")

    # stub 出 smtplib.SMTP
    calls = {}
    class FakeSMTP:
        def __init__(self, host, port, timeout=10):
            calls["init"] = (host, port, timeout)
            self.started = False; self.logged = False; self.sent = False; self.closed=False
        def ehlo(self): pass
        def starttls(self, context=None): self.started = True
        def login(self, u, p): self.logged = True
        def send_message(self, msg): self.sent = True
        def quit(self): self.closed = True

    monkeypatch.setattr(mail_io, "smtplib", types.SimpleNamespace(SMTP=FakeSMTP))

    ret = mail_io.send_email(outbox=outbox, to_addr="x@y.com", subject="StartTLS", body="body")
    assert ret["ok"] is True and ret["via"] == "smtp"
    # 確認 SMTP 流程被走過
    assert calls["init"][0] == "smtp.stub" and calls["init"][1] == 587
    # 讀回 eml 仍存在（審計）
    assert Path(ret["path"]).exists()

def test_receive_imap_offline_returns_empty(monkeypatch):
    monkeypatch.setenv("OFFLINE","1")
    out = mail_io.receive_imap("imap.stub","u","p")
    assert out == []

def test_receive_imap_online_stub(monkeypatch):
    # 走 online stub：OFFLINE=0，替換 imaplib.IMAP4_SSL
    monkeypatch.setenv("OFFLINE","0")
    class FakeIMAP:
        def __init__(self, host, timeout=10): pass
        def login(self, u, p): pass
        def select(self, folder): return ("OK", [b""])
        def search(self, *a): return ("OK", [b"1 2"])
        def fetch(self, i, what):
            from email.message import EmailMessage
            m = EmailMessage(); m["Subject"] = f"Subj{i.decode() if isinstance(i, bytes) else i}"
            return ("OK", [(None, m.as_bytes())])
        def logout(self): pass
    import types as _t
    monkeypatch.setattr(mail_io, "imaplib", _t.SimpleNamespace(IMAP4_SSL=FakeIMAP))
    out = mail_io.receive_imap("imap.stub","u","p", limit=2)
    assert isinstance(out, list) and len(out) == 2
    assert all("subject" in m for m in out)
