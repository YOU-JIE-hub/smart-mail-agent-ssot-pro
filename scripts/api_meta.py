from __future__ import annotations
import json, os
from pathlib import Path
from fastapi import FastAPI
app=FastAPI(title='SMA Meta API')
def load_metrics(task:str):
    base=Path('models')/task
    reg=base/'registry.json'
    if not reg.exists(): return {'status':'missing_registry'}
    active=json.loads(reg.read_text('utf-8')).get('active')
    d=base/'artifacts'/active
    out={'version':active}
    for k in ('metrics.json','thresholds.json','training_meta.json'):
        p=d/k
        if p.exists(): out[k.replace('.json','')]=json.loads(p.read_text('utf-8'))
    return out
@app.get('/debug/model_meta')
def meta(): return {'intent':load_metrics('intent'),'spam':load_metrics('spam'),'kie':load_metrics('kie')}
