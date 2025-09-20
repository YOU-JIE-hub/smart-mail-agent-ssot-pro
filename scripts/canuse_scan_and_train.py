import json, os, re, random, math
from pathlib import Path
from datetime import datetime
from collections import Counter
from typing import Iterable, Tuple, List

import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report
from joblib import dump

random.seed(42); np.random.seed(42)

def iter_jsonl(p: str) -> Iterable[Tuple[str,str]]:
    """盡可能容錯取 text/label；label 轉成 {'spam','ham'}，其他丟掉。"""
    def norm_y(v):
        if isinstance(v, bool): return 'spam' if v else 'ham'
        if isinstance(v, (int, float)): return 'spam' if int(v)==1 else 'ham'
        if isinstance(v, str):
            s=v.strip().lower()
            if s in {'spam','junk','bad','1','true','yes','y'}: return 'spam'
            if s in {'ham','good','not_spam','0','false','no','n','legit'}: return 'ham'
        return None

    with open(p, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try: j=json.loads(line)
            except: continue
            text = j.get('text') or j.get('content') or j.get('body') or \
                   (" ".join([j.get('subject','') or '', j.get('body','') or '']).strip() or None)
            if not text: continue
            y = j.get('label', None)
            if y is None:
                for k in ('target','category','class','tag','intent','is_spam'):
                    if k in j: y=j[k]; break
            y = norm_y(y)
            if y in {'spam','ham'}:
                yield text, y

def load_ds(p: str, max_n=500_000) -> Tuple[List[str], List[str]]:
    X,y=[],[]
    for t,lab in iter_jsonl(p):
        X.append(t); y.append(lab)
        if len(X)>=max_n: break
    return X,y

def main():
    # 優先用你剛剛選到的資料（如果有）
    sel = Path('reports_auto'); cand=None
    if sel.exists():
        latest = sorted(sel.glob('canuse_*/selection.json'))[-1:] or []
        if latest:
            with open(latest[0], 'r', encoding='utf-8') as f:
                jj=json.load(f); cand=(jj['selection']['intent']['path'], jj['selection']['spam']['path'])
    if not cand:
        # 兜底：用之前掃到的兩個
        cand = (
            '/home/youjie/projects/smart-mail-agent/data/prod_merged/train.jsonl',
            '/home/youjie/projects/smart-mail-agent_ssot/data/spam_eval/dataset.jsonl'
        )

    OUTDIR = Path('reports_auto')/f'canuse_fix_{datetime.now().strftime("%Y%m%dT%H%M%S")}'
    OUTDIR.mkdir(parents=True, exist_ok=True)

    results={}
    for name, path in (('intent', cand[0]), ('spam', cand[1])):
        path=str(path)
        X,y = load_ds(path)
        cnt=Counter(y)
        with open(OUTDIR/f'{name}_dist.json', 'w', encoding='utf-8') as f:
            json.dump({'path':path,'counts':cnt,'n':len(y)}, f, ensure_ascii=False, indent=2)

        if len(set(y))<2:
            raise SystemExit(f"[FATAL] {name}: after parsing only one class -> {cnt}. Check label field mapping.")

        # stratified split（保證 train/test 都有兩類）
        Xtr,Xte,ytr,yte = train_test_split(X,y,test_size=0.2,random_state=42,stratify=y)

        # 模型改用 LogReg（有 predict_proba，不用 CalibratedCV，就不會折到單類炸掉）
        pipe = Pipeline([
            ('tfidf', TfidfVectorizer(max_features=200_000, ngram_range=(1,2), min_df=2)),
            ('clf', LogisticRegression(max_iter=2000, n_jobs=1, class_weight='balanced'))
        ])
        pipe.fit(Xtr,ytr)
        yph = pipe.predict(Xte)

        rep = classification_report(yte, yph, output_dict=True)
        with open(OUTDIR/f'{name}_report.json','w',encoding='utf-8') as f:
            json.dump(rep,f,ensure_ascii=False,indent=2)

        out_pkl = OUTDIR/f'{name}_model.pkl'
        dump(pipe, out_pkl)
        results[name] = {'path': path, 'model': str(out_pkl), 'report': rep}

    with open(OUTDIR/'SUMMARY.json','w',encoding='utf-8') as f:
        json.dump(results,f,ensure_ascii=False,indent=2)

    print(json.dumps({'outdir':str(OUTDIR),'ok':True}, ensure_ascii=False))
if __name__ == "__main__":
    main()
