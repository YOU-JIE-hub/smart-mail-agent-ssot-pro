from __future__ import annotations
import os, sys, subprocess, pathlib
from email.message import EmailMessage
def make_eml_from_txt(txt: pathlib.Path) -> EmailMessage:
    body=txt.read_text(encoding="utf-8",errors="ignore")
    subj="manual_test"
    for line in body.splitlines():
        if line.lower().startswith("subject:"): subj=line.split(":",1)[1].strip() or subj; break
    m=EmailMessage(); m["Subject"]=subj; m["From"]=os.getenv("SMA_SMTP_USER") or "noreply@example.com"; m.set_content(body); return m
def save_eml(msg: EmailMessage, dest: pathlib.Path)->pathlib.Path:
    dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(msg.as_bytes()); return dest
def main():
    import argparse; ap=argparse.ArgumentParser()
    ap.add_argument("--run-dir",required=True); ap.add_argument("--to",required=True); ap.add_argument("--force",action="store_true")
    a=ap.parse_args(); rd=pathlib.Path(a.run_dir); outbox=rd/"rpa_out"/"email_outbox"; sent=rd/"rpa_out"/"email_sent"
    outbox.mkdir(parents=True,exist_ok=True); sent.mkdir(parents=True,exist_ok=True)
    wl={e.strip().lower() for e in os.getenv("SMA_EMAIL_WHITELIST","").split(",") if e.strip()}
    if wl and a.to.lower() not in wl: print(f"[DENY] {a.to} not in whitelist={','.join(sorted(wl))}"); sys.exit(0)
    mode=os.getenv("SMA_SMTP_MODE","smtp"); user=os.getenv("SMA_SMTP_USER"); pwd=os.getenv("SMA_SMTP_PASS")
    if mode!="smtp" or not (user and pwd):
        created=skipped=0
        for txt in sorted(outbox.glob("*.txt")):
            eml=sent/((txt.stem[:80] or "mail")+".eml")
            if eml.exists() and not a.force: skipped+=1; continue
            m=make_eml_from_txt(txt); m["To"]=a.to; save_eml(m, eml); created+=1
        print(f"[OUTBOX-ONLY] run={rd.name} created={created} skipped={skipped}"); return
    cmd=[sys.executable,"tools/send_with_intent_attachments.py","--run-dir",str(rd),"--to",a.to]
    if a.force: cmd.append("--force"); print("[DELEGATE]"," ".join(cmd)); subprocess.run(cmd,check=False)
if __name__=="__main__": main()
