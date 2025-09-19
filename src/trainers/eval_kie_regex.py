from __future__ import annotations
import json,regex as re
from pathlib import Path
from scripts.common_io import read_jsonl, ensure_registry, write_json
import numpy as np

DATE=Path('.').resolve().name  # not used
ROOT=Path.cwd(); TODAY=os.environ.get('TODAY','')
ART=ROOT/'models'/'kie'/'artifacts'/f'v{TODAY}'
ART.mkdir(parents=True, exist_ok=True)
p = ROOT/'data'/'kie_eval'/'gold_merged.jsonl'
rows=read_jsonl(p)
def extract(text):
    m_id=re.search(r'\b(?:SO|PO|INV)[-_]?[A-Z0-9]{3,}\b', text)
    m_amt=re.search(r'(?:NT\$|TWD|\$)?\s*([0-9][\d,]*(?:\.\d{1,2})?)', text)
    m_phone=re.search(r'(?:\+?886[-\s]?|0)\d{1,2}[-\s]?\d{3,4}[-\s]?\d{3,4}', text)
    out={}
    if m_id: out['order_id']=m_id.group(0).replace(',','')
    if m_amt: out['amount']=m_amt.group(1).replace(',','')
    if m_phone: out['phone']=m_phone.group(0)
    return out
def f1(p,r): return 0.0 if p+r==0 else 2*p*r/(p+r)
tp=fp=fn=0; field_scores={}
for r in rows:
    gold = (r.get('labels') or {})
    pred = extract(r.get('text',''))
    for k in set(list(gold.keys())+list(pred.keys())):
        g = str(gold.get(k,'')); d=str(pred.get(k,''))
        if d and g:
            if g==d: tp+=1; field_scores[k]=field_scores.get(k,[])+[(1,1,1)]
            else: fp+=1; fn+=1; field_scores[k]=field_scores.get(k,[])+[(0,0,0)]
        elif d and not g: fp+=1; field_scores[k]=field_scores.get(k,[])+[(0,0,0)]
        elif g and not d: fn+=1; field_scores[k]=field_scores.get(k,[])+[(0,0,0)]
prec = 0.0 if (tp+fp)==0 else tp/(tp+fp)
rec  = 0.0 if (tp+fn)==0 else tp/(tp+fn)
macro_f1 = f1(prec,rec)
em = 0
for r in rows:
    gold = (r.get('labels') or {})
    pred = extract(r.get('text',''))
    em += 1 if pred==gold and gold else 0
metrics={'macro_f1':macro_f1,'exact_match': (em/len(rows) if rows else 0.0),'n':len(rows)}
write_json(ART/'metrics.json', metrics)
write_json(ART/'thresholds.json', {})
(ART/'MODEL_CARD.md').write_text('# Model Card — KIE (Regex baseline)\n', 'utf-8')
write_json(ART/'training_meta.json', {'date':TODAY,'data_path':str(p),'n_total':len(rows),'note':'regex baseline'})
ensure_registry('kie', f'v{os.environ.get("TODAY","")}')
print('[OK] kie eval ->', ART.as_posix())
