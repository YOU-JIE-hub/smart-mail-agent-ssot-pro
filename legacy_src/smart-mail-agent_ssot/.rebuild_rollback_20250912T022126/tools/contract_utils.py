from __future__ import annotations
import os, json, mimetypes
from pathlib import Path
from email.message import EmailMessage

def load_contract(path="artifacts_prod/intent_contract.json"):
    p=Path(path)
    if not p.exists():
        return {}
    try:
        obj=json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}
    intents=obj.get("intents",[]) or []
    return { it.get("name"): it for it in intents if isinstance(it, dict) and it.get("name") }

def apply_subject_tag(msg:EmailMessage, rule:dict):
    tag=(rule or {}).get("subject_tag")
    if not tag: return
    subj=msg.get("Subject","")
    if tag not in subj:
        msg.replace_header("Subject", f"{tag} {subj}".strip())

def add_attachment(msg:EmailMessage, file_path:str):
    try:
        data=Path(file_path).read_bytes()
    except Exception:
        return
    ctype,_=mimetypes.guess_type(file_path)
    if not ctype: ctype="application/octet-stream"
    maintype,subtype=ctype.split("/",1)
    msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=os.path.basename(file_path))

def add_inline_html(msg:EmailMessage, html_path:str):
    p=Path(html_path)
    if not p.exists(): return
    html=p.read_text(encoding="utf-8", errors="ignore")
    msg.add_alternative(html, subtype="html")

def apply_contract_to_message(msg:EmailMessage, intent:str, contract_map:dict):
    rule=(contract_map or {}).get(intent)
    if not rule: return
    apply_subject_tag(msg, rule)
    for ap in (rule.get("attachments") or []):
        if os.path.exists(ap): add_attachment(msg, ap)
    inline=rule.get("inline")
    if inline: add_inline_html(msg, inline)
