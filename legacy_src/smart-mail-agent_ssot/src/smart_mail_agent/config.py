from __future__ import annotations
import os
from dataclasses import dataclass
from typing import List
@dataclass(frozen=True)
class Cfg:
    smtp_mode: str; smtp_host: str; smtp_port: int; smtp_tls: str
    smtp_user: str; smtp_pass: str; email_whitelist: List[str]
    action_cap_send_email: int; rag_backend: str; rag_topk: int; kb_dir: str
def _split_csv(s:str)->List[str]: return [x.strip() for x in s.split(",") if x.strip()]
def cfg()->Cfg:
    return Cfg(
        smtp_mode=os.getenv("SMA_SMTP_MODE","outbox"),
        smtp_host=os.getenv("SMA_SMTP_HOST","smtp.gmail.com"),
        smtp_port=int(os.getenv("SMA_SMTP_PORT","587")),
        smtp_tls=os.getenv("SMA_SMTP_TLS","starttls"),
        smtp_user=os.getenv("SMA_SMTP_USER","h125872359@gmail.com"),
        smtp_pass=os.getenv("SMA_SMTP_PASS",""),
        email_whitelist=_split_csv(os.getenv("SMA_EMAIL_WHITELIST","h125872359@gmail.com")),
        action_cap_send_email=int(os.getenv("SMA_ACTION_CAP_SEND_EMAIL","200")),
        rag_backend=os.getenv("SMA_RAG_BACKEND","bm25"),
        rag_topk=int(os.getenv("SMA_RAG_TOPK","3")),
        kb_dir=os.getenv("SMA_KB_DIR","kb/faq"),
    )
