#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, random, zipfile
from pathlib import Path
from email import policy
from email.parser import BytesParser

def walk_msg_text_atts(msg):
    texts, atts = [], []
    if msg.is_multipart():
        for part in msg.walk():
            cd = part.get_content_disposition()
            ctype = part.get_content_type() or ""
            if cd == "attachment":
                atts.append(part.get_filename() or "attachment")
            elif ctype.startswith("text/"):
                try: texts.append(part.get_content().strip())
                except Exception:
                    try: texts.append(part.get_payload(decode=True).decode(errors="ignore"))
                    except Exception: pass
    else:
        ctype = msg.get_content_type() or ""
        if ctype.startswith("text/"):
            try: texts.append(msg.get_content().strip())
            except Exception:
                try: texts.append(msg.get_payload(decode=True).decode(errors="ignore"))
                except Exception: pass
    return "\n\n".join([t for t in texts if t]), atts

def parse_eml_bytes(b: bytes):
    try:
        msg = BytesParser(policy=policy.default).parsebytes(b)
        subj = msg.get("subject") or ""
        sender = msg.get("from") or ""
        body, atts = walk_msg_text_atts(msg)
        if not body:
            try: body = msg.get_payload(decode=True).decode(errors="ignore")
            except Exception: body = ""
        return subj[:500], body, sender, atts
    except Exception:
        # 極端退路：直接解碼
        for enc in ("utf-8","gb18030","big5","latin-1"):
            try:
                txt = b.decode(enc)
                break
            except Exception:
                txt = b.decode("utf-8", errors="ignore")
        return "", txt, "", []

def convert_zip(zip_path: Path):
    with zipfile.ZipFile(zip_path) as z:
        files = [n for n in z.namelist()
                 if (n.startswith("data/spam/") or n.startswith("data/normal/")) and not n.endswith("/")]
        rows = []
        for n in files:
            label = "spam" if n.startswith("data/spam/") else "ham"
            try:
                b = z.read(n)
                subj, body, sender, atts = parse_eml_bytes(b)
                rows.append({"id": n, "subject": subj, "body": body, "from": sender,
                             "attachments": atts, "label": label})
            except Exception:
                pass
    return rows

def stratified_split(rows, train=0.70, val=0.15, seed=20250830):
    random.seed(seed)
    by = {"ham": [], "spam": []}
    for r in rows:
        by[r["label"]].append(r)
    parts = {}
    for lbl, arr in by.items():
        idx = list(range(len(arr))); random.shuffle(idx)
        n = len(arr); n_tr = int(n*train); n_va = int(n*val)
        parts[lbl] = {
            "train": [arr[i] for i in idx[:n_tr]],
            "val":   [arr[i] for i in idx[n_tr:n_tr+n_va]],
            "test":  [arr[i] for i in idx[n_tr+n_va:]],
        }
    out = { split: parts["ham"][split] + parts["spam"][split] for split in ("train","val","test") }
    for split in out:
        random.shuffle(out[split])
    return out

def emit_jsonl(rows, fp: Path):
    fp.parent.mkdir(parents=True, exist_ok=True)
    with open(fp, "w", encoding="utf-8") as w:
        for r in rows:
            w.write(json.dumps(r, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True)
    ap.add_argument("--outdir", default="data/trec06c_zip")
    a = ap.parse_args()

    rows = convert_zip(Path(a.zip))
    from collections import Counter
    cnt = Counter([r["label"] for r in rows])
    print(f"[READ] total={len(rows)} | ham={cnt.get('ham',0)} spam={cnt.get('spam',0)}")

    outdir = Path(a.outdir); outdir.mkdir(parents=True, exist_ok=True)
    emit_jsonl(rows, outdir/"all.jsonl")

    splits = stratified_split(rows)
    for name, subset in splits.items():
        emit_jsonl(subset, outdir/f"{name}.jsonl")
        c = Counter([r["label"] for r in subset])
        print(f"[WRITE] {name}.jsonl -> {len(subset)} (ham={c.get('ham',0)} spam={c.get('spam',0)})")

    print("[OK] done:", a.outdir)
