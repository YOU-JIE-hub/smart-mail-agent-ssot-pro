from pathlib import Path
import os, subprocess, sys, time
def latest_run_dir()->Path:
    base=Path("reports_auto/e2e_mail"); runs=sorted([p for p in base.glob("*") if p.is_dir()])
    return runs[-1]
def test_whitelist_and_resend():
    os.environ["SMA_SMTP_MODE"]="outbox"; os.environ["SMA_EMAIL_WHITELIST"]="allowed@example.com"
    ts=time.strftime("%Y%m%dT%H%M%S")
    subprocess.run([sys.executable,"-m","smart_mail_agent.cli.e2e","--eml-dir","tests/_data/eml",
                    "--out-root",f"reports_auto/e2e_mail/{ts}","--db-path","db/sma.sqlite",
                    "--ndjson",f"reports_auto/events/{ts}.ndjson"], check=False)
    rd=latest_run_dir(); outbox=rd/"rpa_out"/"email_outbox"; outbox.mkdir(parents=True,exist_ok=True)
    (outbox/"t.txt").write_text("Subject: T\nbody",encoding="utf-8")
    r=subprocess.run([sys.executable,"tools/send_outbox_guard.py","--run-dir",str(rd),"--to","nope@example.com"],capture_output=True,text=True)
    assert "not in whitelist" in (r.stdout+r.stderr)
    subprocess.run([sys.executable,"tools/send_outbox_guard.py","--run-dir",str(rd),"--to","allowed@example.com"], check=False)
    before=len(list((rd/"rpa_out"/"email_sent").glob("*.eml")))
    subprocess.run([sys.executable,"tools/send_outbox_guard.py","--run-dir",str(rd),"--to","allowed@example.com"], check=False)
    after=len(list((rd/"rpa_out"/"email_sent").glob("*.eml")))
    assert before==after
