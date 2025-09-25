#!/usr/bin/env python3
# 檔案位置：src/smart_mail_agent/spam/train/features.py
# 模組用途：抽取垃圾信規則特徵（離線），供訓練與推論使用
from __future__ import annotations
import re, math
from pathlib import Path
from typing import Dict, Any, Iterable, List
import yaml

URL_RE = re.compile(r'https?://[^\s)]+', re.I)
EMAIL_RE = re.compile(r'[\w\.-]+@([\w\.-]+)')
MONEY_RE = re.compile(r'(\$|USD|NT\$|NTD|US\$|HK\$|EUR|GBP)', re.I)
NON_ASCII_RE = re.compile(r'[^\x00-\x7F]')

def load_rules(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _domain_from_email(addr: str) -> str:
    m = EMAIL_RE.search(addr or "")
    return m.group(1).lower() if m else ""

def _tld(host: str) -> str:
    parts = host.lower().split(".")
    return parts[-1] if len(parts) >= 2 else ""

def _url_hosts(text: str) -> List[str]:
    hosts = []
    for m in URL_RE.findall(text or ""):
        h = re.sub(r'^https?://', '', m, flags=re.I).split('/')[0]
        if h: hosts.append(h.lower())
    return hosts

def extract(sample: dict, rules: dict) -> Dict[str, float]:
    subject = (sample.get("subject") or "").strip()
    body = (sample.get("body") or "").strip()
    sender = (sample.get("from") or "").strip()
    att = sample.get("attachments") or []

    text = f"{subject}\n{body}"
    tokens = re.split(r'\s+', text.strip())
    tok_n = max(1, len([t for t in tokens if t]))

    urls = URL_RE.findall(text)
    url_n = len(urls)
    url_ratio = url_n / float(tok_n)

    hosts = _url_hosts(text)
    tl_ds = { _tld(h) for h in hosts }

    kw = rules.get("keywords") or []
    kw_hits = 0
    lower_text = text.lower()
    for k in kw:
        if (k or "").lower() in lower_text:
            kw_hits += 1

    bl_senders = set((rules.get("blacklist_senders") or []))
    bl_domains = set((rules.get("blacklist_domains") or []))
    sender_domain = _domain_from_email(sender)
    sender_black = 1.0 if sender in bl_senders or sender_domain in bl_domains else 0.0

    susp_tld = set((rules.get("suspicious_tld") or []))
    risky_tld_hits = sum(1 for t in tl_ds if t in susp_tld)

    risky_ext = set((rules.get("attachment_risky_ext") or []))
    att_risky_hits = 0
    for a in att:
        ext = (str(a).rsplit(".", 1)[-1]).lower() if "." in str(a) else ""
        if ext in risky_ext:
            att_risky_hits += 1

    money_symbols = len(MONEY_RE.findall(text))
    non_ascii_ratio = len(NON_ASCII_RE.findall(text)) / max(1.0, len(text))

    return {
        "keyword_hits": float(kw_hits),
        "url_ratio": float(url_ratio),
        "risky_tld_hits": float(risky_tld_hits),
        "attachment_risky_hits": float(att_risky_hits),
        "money_symbols": float(money_symbols),
        "non_ascii_ratio": float(non_ascii_ratio),
        "sender_black": float(sender_black),
        "bias": 1.0
    }
