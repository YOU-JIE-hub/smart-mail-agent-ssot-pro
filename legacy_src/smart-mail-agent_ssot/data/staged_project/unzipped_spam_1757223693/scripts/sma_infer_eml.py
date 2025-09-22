#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, joblib
from pathlib import Path
from email import policy
from email.parser import BytesParser
from sklearn.pipeline import make_pipeline
from _spam_common import signals

def parse_eml(fp:Path):
    m=BytesParser(policy=policy.default).parse(open(fp,'rb'))
    subj = m.get('subject') or ''
    texts, atts = [], []
    if m.is_multipart():
        for part in m.walk():
            cd=part.get_content_disposition(); ct=part.get_content_type() or ""
            if cd=='attachment': atts.append(part.get_filename() or 'attachment')
            elif ct.startswith('text/'):
                try: texts.append(part.get_content().strip())
                except Exception:
                    try: texts.append(part.get_payload(decode=True).decode(errors='ignore'))
                    except Exception: pass
    else:
        if m.get_content_type().startswith('text/'):
            try: texts.append(m.get_content().strip())
            except Exception:
                try: texts.append(m.get_payload(decode=True).decode(errors='ignore'))
                except Exception: pass
    return subj, "\n\n".join([t for t in texts if t]), atts

ap=argparse.ArgumentParser()
ap.add_argument("path", help=".eml 檔或資料夾")
ap.add_argument("--model_dir", default="artifacts_prod")
ap.add_argument("--out", default="reports_auto/predict_eml.tsv")
a=ap.parse_args()

mdlp=Path(a.model_dir)/"model_pipeline.pkl"
if not mdlp.exists(): mdlp=Path(a.model_dir)/"text_lr_platt.pkl"
clf=joblib.load(mdlp)

thr=0.44; sigmin=3
thrj=Path(a.model_dir)/"ens_thresholds.json"
if thrj.exists():
    try:
        o=json.loads(thrj.read_text()); thr=float(o.get("threshold",thr)); sigmin=int(o.get("signals_min",sigmin))
    except Exception: pass

paths=[Path(a.path)]
if Path(a.path).is_dir(): paths=sorted(Path(a.path).rglob("*.eml"))
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
with open(a.out,"w",encoding="utf-8") as w:
    w.write("path\tprob\tpred_text\tsignals\tpred_rule\tpred_ens\tsubject\n")
    for fp in paths:
        try:
            subj, body, atts = parse_eml(fp)
            prob=float(clf.predict_proba([f"{subj}\n{body}"])[:,1][0])
            s=signals({"subject":subj,"body":body,"attachments":atts})
            pt=1 if prob>=thr else 0
            pr=1 if s>=sigmin else 0
            pe=1 if (pt or pr) else 0
            w.write(f"{fp}\t{prob:.6f}\t{pt}\t{s}\t{pr}\t{pe}\t{subj[:160].replace('\t',' ')}\n")
        except Exception as ex:
            w.write(f"{fp}\tERROR:{ex}\t\t\t\t\t\n")
print("[OK] wrote", a.out)
