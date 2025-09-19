from __future__ import annotations
import json,hashlib,os,random,sqlite3
from pathlib import Path
import pandas as pd

ROOT=Path(os.environ.get('SMA_ROOT',os.getcwd()))
LOGS=ROOT/'reports_auto'/'logs'; LOGS.mkdir(parents=True,exist_ok=True)
STATUS=ROOT/'reports_auto'/'status'; STATUS.mkdir(parents=True,exist_ok=True)

def sha256_head(p,cap=4*1024*1024):
    p=Path(p); h=hashlib.sha256(); r=0
    with open(p,'rb') as f:
        while True:
            b=f.read(1024*1024)
            if not b: break
            h.update(b); r+=len(b)
            if r>=cap: h.update(b'__TRUNCATED__'); break
    return h.hexdigest()

def safe_id(text:str)->str:
    s=(text or '')[:4096].encode('utf-8','ignore')
    return hashlib.sha1(s).hexdigest()[:12]

def read_jsonl(p):
    arr=[]
    for ln in Path(p).read_text('utf-8').splitlines():
        if not ln.strip(): continue
        o=json.loads(ln)
        if 'id' not in o or not o['id']:
            o['id']=safe_id(o.get('text',''))
        arr.append(o)
    return arr

def ensure_registry(task:str, version:str):
    base=ROOT/'models'/task
    base.mkdir(parents=True,exist_ok=True)
    reg=base/'registry.json'
    reg.write_text(json.dumps({'active':version},ensure_ascii=False,indent=2),'utf-8')
    latest=base/'LATEST'; tgt=base/'artifacts'/version
    latest.exists() and latest.unlink()
    tgt.mkdir(parents=True,exist_ok=True)
    latest.symlink_to(tgt)

def write_json(p, obj):
    Path(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2),'utf-8')
