#!/usr/bin/env python3
import re, json, sys
from typing import Dict, Any, List

RX = {
    "amount": re.compile(r"(?:NT\$|USD|US\$)?\s*<AMOUNT>|(?:NT\$|USD|US\$)\s*[\d,]+(?:\.\d+)?|[\d,]+(?:\.\d+)?\s*(?:USD|US\$)", re.I),
    "currency": re.compile(r"\b(?:NT\$|USD|US\$)\b", re.I),
    "seats": re.compile(r"\b(\d{1,4})\s*(?:seats?|users?)\b", re.I),
    "stores": re.compile(r"\b(\d{1,4})\s*(?:stores?|店|店點)\b", re.I),
    "dates": re.compile(r"\b(?:EOD|EOW|EOM|Q[1-4]|UAT|prod|production|sandbox|10/\d{1,2}|11/\d{1,2}|[12]\d{3}-\d{1,2}-\d{1,2})\b", re.I),
    "env": re.compile(r"\b(?:sandbox|UAT|prod|production)\b", re.I),
    "http": re.compile(r"/v\d+/\w+"),
    "status": re.compile(r"\b(429|500)\b"),
    "sla_pct": re.compile(r"\b99\.(?:9{1,2})%\b"),
    "rto": re.compile(r"\bRTO\s*\d+\s*(?:m|min|分鐘)?\b", re.I),
    "rpo": re.compile(r"\bRPO\s*\d+\s*(?:m|min|分鐘)?\b", re.I),
    "po": re.compile(r"\bPO\b"),
    "grn": re.compile(r"\bGRN\b"),
    "invoice": re.compile(r"\b發票|invoice\b"),
    "security": re.compile(r"\b(?:OTP|SSO|SAML|TLS|CORS|webhook)\b", re.I),
    "placeholders": re.compile(r"<(EMAIL|PHONE|URL|ADDR|NAME|COMPANY|ORDER_ID|INVOICE_NO|AMOUNT)>")
}

def uniq(seq: List[str]) -> List[str]:
    out=[]; seen=set()
    for x in seq:
        k=x.lower()
        if k not in seen:
            seen.add(k); out.append(x)
    return out

def extract_fields(text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    # 金額與幣別
    amt = RX["amount"].findall(text)
    cur = RX["currency"].findall(text)
    if amt: out["amounts"] = uniq(amt)
    if cur: out["currencies"] = uniq(cur)
    # 數量/環境/接口狀態
    m = RX["seats"].findall(text);  s = RX["stores"].findall(text)
    if m: out["seats"] = [int(x) for x in m]
    if s: out["stores"] = [int(x) for x in s]
    env = RX["env"].findall(text);  http = RX["http"].findall(text); st = RX["status"].findall(text)
    if env: out["env"] = uniq(env)
    if http: out["apis"] = uniq(http)
    if st: out["http_errors"] = uniq(st)
    # SLA / RTO / RPO
    sla = RX["sla_pct"].findall(text); rto = RX["rto"].findall(text); rpo = RX["rpo"].findall(text)
    if sla: out["sla"] = uniq(sla)
    if rto: out["rto"] = uniq(rto)
    if rpo: out["rpo"] = uniq(rpo)
    # PO/GRN/發票
    if RX["po"].search(text): out["has_po"] = True
    if RX["grn"].search(text): out["has_grn"] = True
    if RX["invoice"].search(text): out["mentions_invoice"] = True
    # 安全/技術關鍵字
    sec = RX["security"].findall(text)
    if sec: out["security"] = uniq(sec)
    # 佔位符統計
    ph = RX["placeholders"].findall(text)
    if ph: out["placeholders"] = uniq(ph)
    # 日期/時點關鍵詞
    dt = RX["dates"].findall(text)
    if dt: out["time_tokens"] = uniq(dt)
    return out

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--text", help="single text")
    ap.add_argument("--input", help="jsonl with {text:...}")
    args=ap.parse_args()
    rows=[]
    if args.text:
        rows=[{"text": args.text}]
    elif args.input:
        with open(args.input,"r",encoding="utf-8") as f:
            for ln in f:
                if ln.strip(): rows.append(json.loads(ln))
    else:
        for ln in sys.stdin:
            t=ln.strip()
            if t: rows.append({"text": t})
    for r in rows:
        f = extract_fields(r["text"])
        print(json.dumps({"text": r["text"], "fields": f}, ensure_ascii=False))
if __name__=="__main__":
    main()
