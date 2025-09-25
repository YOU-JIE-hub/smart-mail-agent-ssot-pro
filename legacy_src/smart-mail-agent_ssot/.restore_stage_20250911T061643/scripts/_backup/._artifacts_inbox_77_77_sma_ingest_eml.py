#!/usr/bin/env python3
# 讀取 .eml 或資料夾，輸出 JSONL：{id, from, subject, body, attachments[]}
import argparse, json, sys, re
from pathlib import Path
from email import policy
from email.parser import BytesParser
from email.header import decode_header
from email.utils import getaddresses

def dec_hdr(x):
    if not x: return ""
    try:
        parts = decode_header(x)
        out=[]
        for s,enc in parts:
            if isinstance(s, bytes):
                try: out.append(s.decode(enc or "utf-8", errors="ignore"))
                except: out.append(s.decode("utf-8", errors="ignore"))
            else:
                out.append(str(s))
        return "".join(out)
    except:
        return str(x)

def html2text(h):
    if not h: return ""
    # 非重度轉換，demo 夠用：殺 script/style、去標籤
    h = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", h)
    h = re.sub(r"(?is)<br\\s*/?>", "\n", h)
    h = re.sub(r"(?is)</p>", "\n", h)
    h = re.sub(r"(?is)<[^>]+>", " ", h)
    return re.sub(r"[ \\t\\x0b\\r\\f]+", " ", h).strip()

def extract_text(msg):
    texts=[]
    html=[]
    for part in msg.walk():
        ctype = part.get_content_type()
        disp  = (part.get_content_disposition() or "").lower()
        if disp == "attachment": 
            continue
        if ctype == "text/plain":
            try: texts.append(part.get_content().strip())
            except: 
                try: texts.append(part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore").strip())
                except: pass
        elif ctype == "text/html":
            try: html.append(part.get_content())
            except:
                try: html.append(part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore"))
                except: pass
    body = "\n".join(x for x in texts if x) or html2text("\n".join(html))
    return body.strip()

def extract_atts(msg):
    out=[]
    for part in msg.walk():
        disp = (part.get_content_disposition() or "").lower()
        if disp == "attachment":
            fn = part.get_filename()
            out.append(dec_hdr(fn) if fn else "")
    return out

def parse_eml(fp: Path):
    with fp.open("rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)
    sub = dec_hdr(msg.get("Subject"))
    frm = ", ".join([f"{n} <{e}>" if n else e for n,e in getaddresses([msg.get("From","")])])
    body = extract_text(msg)
    atts = extract_atts(msg)
    return {"id": fp.stem, "from": frm, "subject": sub, "body": body, "attachments": atts}

def walk_inputs(p: Path):
    if p.is_file() and p.suffix.lower()==".eml":
        yield p
    elif p.is_dir():
        for q in sorted(p.rglob("*.eml")):
            yield q

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help=".eml 檔或資料夾")
    ap.add_argument("--out", required=True, help="輸出 JSONL 檔")
    a=ap.parse_args()
    src=Path(a.input); dst=Path(a.out)
    rows=[]
    for eml in walk_inputs(src):
        try:
            rows.append(parse_eml(eml))
        except Exception as e:
            print(f"[WARN] parse fail: {eml} => {e}", file=sys.stderr)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8") as w:
        for r in rows: w.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[INGEST] {len(rows)} mails -> {dst}")
if __name__=="__main__": main()
