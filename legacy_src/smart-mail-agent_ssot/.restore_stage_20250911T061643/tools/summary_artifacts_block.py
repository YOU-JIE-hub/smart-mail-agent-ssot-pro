from __future__ import annotations
from pathlib import Path; import json, os
def read_manifest():
    p=Path("artifacts_prod/manifest.json")
    return json.loads(p.read_text("utf-8")) if p.exists() else {"version":"(no-manifest)","artifacts":[]}
def block(rd: Path)->str:
    m=read_manifest(); wl=os.getenv("SMA_EMAIL_WHITELIST",""); smtp=os.getenv("SMA_SMTP_MODE","smtp")
    lines=["## Artifacts & Runtime",f"- manifest.version: `{m['version']}`",f"- smtp.mode: `{smtp}`  whitelist: `{wl}`","",
           "| file | size | sha256 |","|---|---:|---|"]
    for it in m["artifacts"][:50]: lines.append(f"| {it['name']} | {it['size']} | `{it['sha256'][:16]}…` |")
    return "\n".join(lines)+"\n"
def main():
    import argparse; ap=argparse.ArgumentParser(); ap.add_argument("--run-dir", required=True); a=ap.parse_args()
    rd=Path(a.run_dir); sm=rd/"SUMMARY.md"; sm.write_text((sm.read_text("utf-8") if sm.exists() else "# SUMMARY\n")+"\n"+block(rd), "utf-8")
    print(f"[OK] appended artifacts block -> {sm}")
if __name__=="__main__": main()
