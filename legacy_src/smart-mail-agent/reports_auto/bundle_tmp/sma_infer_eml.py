#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
from email import policy
from email.parser import BytesParser
import joblib, numpy as np

RE_URL=re.compile(r"https?://[^\s)>\]]+",re.I)
SUS_TLD={".zip",".xyz",".top",".cam",".shop",".work",".loan",".country",".gq",".tk",".ml",".cf"}
SUS_EXT={".zip",".rar",".7z",".exe",".js",".vbs",".bat",".cmd",".htm",".html",".lnk",".iso",".docm",".xlsm",".pptm",".scr"}
KW=["重設密碼","驗證","帳戶異常","登入異常","補件","逾期","海關","匯款","退款","發票","稅務","罰款",
    "verify","reset","2fa","account","security","login","signin","update","confirm","invoice","payment","urgent","limited","verify your account"]

def spam_signals(subj:str, body:str, atts:list[str]) -> int:
    t=(subj or "")+" "+(body or ""); tl=t.lower()
    urls=RE_URL.findall(tl)
    sig=0
    if urls: sig+=1
    if any(u.lower().endswith(t) for u in urls for t in SUS_TLD): sig+=1
    if any(k in tl for k in KW): sig+=1
    atts=[(a or "").lower() for a in atts if a]
    if any(a.endswith(ext) for a in atts for ext in SUS_EXT): sig+=1
    if ("account" in tl) and (("verify" in tl) or ("reset" in tl) or ("login" in tl) or ("signin" in tl)): sig+=1
    if ("帳戶" in tl) and (("驗證" in tl) or ("重設" in tl) or ("登入" in tl)): sig+=1
    return sig

def parse_eml(fp:Path):
    msg=BytesParser(policy=policy.default).parse(open(fp,"rb"))
    subj=msg.get("subject") or ""
    sender=msg.get("from") or ""
    texts=[]; atts=[]
    if msg.is_multipart():
        for part in msg.walk():
            cd=part.get_content_disposition()
            ct=part.get_content_type() or ""
            if cd=="attachment": atts.append(part.get_filename() or "attachment")
            elif ct.startswith("text/"):
                try: texts.append(part.get_content().strip())
                except Exception:
                    try: texts.append(part.get_payload(decode=True).decode(errors="ignore"))
                    except Exception: pass
    else:
        if msg.get_content_type().startswith("text/"):
            try: texts.append(msg.get_content().strip())
            except Exception:
                try: texts.append(msg.get_payload(decode=True).decode(errors="ignore"))
                except Exception: pass
    body="\n\n".join([x for x in texts if x])
    return subj, body, sender, atts

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("path", help=".eml 檔或資料夾")
    ap.add_argument("--model", default="artifacts_prod/text_lr_platt.pkl")
    ap.add_argument("--thr", type=float, default=None)
    ap.add_argument("--signals_min", type=int, default=None)
    ap.add_argument("--out", default="reports_auto/predict_eml.tsv")
    a=ap.parse_args()

    thr_file=json.load(open("artifacts_prod/ens_thresholds.json"))
    thr=a.thr if a.thr is not None else float(thr_file["threshold"])
    sig_min=a.signals_min if a.signals_min is not None else int(thr_file["signals_min"])

    clf=joblib.load(a.model)
    p=Path(a.path)
    files=[p] if p.is_file() else sorted([x for x in p.rglob("*.eml")])

    import csv
    with open(a.out,"w",encoding="utf-8",newline="") as w:
        wr=csv.writer(w, delimiter='\t')
        wr.writerow(["file","prob_spam","signals","pred"])
        for fp in files:
            subj, body, sender, atts = parse_eml(fp)
            X=[(subj+" \n "+body)]
            prob=float(clf.predict_proba(X)[0,1])
            sig=spam_signals(subj, body, atts)
            pred = 1 if (prob>=thr or sig>=sig_min) else 0
            wr.writerow([str(fp), f"{prob:.4f}", sig, "spam" if pred else "ham"])
    print(f"[OK] wrote {a.out}  (N={len(files)})  thr={thr}  signals_min={sig_min}")

if __name__=="__main__": main()
