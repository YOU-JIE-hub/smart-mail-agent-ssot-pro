from __future__ import annotations
import json, argparse
from pathlib import Path
def load_contract(p:Path)->dict:
    if not p.exists(): return {}
    obj=json.loads(p.read_text("utf-8",errors="ignore"))
    m={}
    for it in obj.get("intents",[]):
        n=it.get("name"); tag=it.get("subject_tag")
        if isinstance(n,str) and isinstance(tag,str):
            m[n]=tag
    return m
def ensure_tag(text:str, tag:str)->str:
    lines=text.splitlines()
    if not lines: return f"Subject: {tag}\n"
    if lines[0].lower().startswith("subject:"):
        subj=lines[0].split(":",1)[1].strip()
        if tag not in subj:
            lines[0]=f"Subject: {tag} {subj}".strip()
        return "\n".join(lines)+"\n"
    else:
        return f"Subject: {tag}\n"+text
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--contract", default="artifacts_prod/intent_contract.json")
    args=ap.parse_args()
    mapping=load_contract(Path(args.contract))
    outbox=Path(args.run_dir)/"rpa_out"/"email_outbox"
    if not outbox.exists(): return
    for txt in sorted(outbox.glob("*.txt")):
        name=txt.stem
        tag=mapping.get(name)
        if not tag: continue
        txt.write_text(ensure_tag(txt.read_text("utf-8",errors="ignore"), tag), encoding="utf-8")
        print("[TAGGED]", txt.name, "->", tag)
if __name__=="__main__":
    main()
