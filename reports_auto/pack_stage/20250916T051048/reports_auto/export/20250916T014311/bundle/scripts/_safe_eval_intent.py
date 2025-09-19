#!/usr/bin/env python
import argparse, json, re, pathlib
import joblib
import numpy as np

# ---- shims：給當初訓練時掛在 __main__ 的特徵函式用 ----
def _ensure_list(X):
    try:
        import numpy as _np
        if isinstance(X, (_np.ndarray,)): X = X.tolist()
    except Exception:
        pass
    if isinstance(X, (str, bytes)): return [X]
    try:
        iter(X); return list(X)
    except Exception:
        return [X]

def rules_feat(X, *args, **kwargs):
    L=_ensure_list(X); return [ {} for _ in L ]

def prio_feat(X, *args, **kwargs):
    L=_ensure_list(X); return [ {} for _ in L ]

def bias_feat(X, *args, **kwargs):
    L=_ensure_list(X); return [ {} for _ in L ]

def load_pipeline_with_auto_shims(pkl_path, max_retry=10):
    """遇到 Can't get attribute 'XXX' on '__main__' 時，動態注入同名 shim 再重試。"""
    p=pathlib.Path(pkl_path)
    last=None
    for _ in range(max_retry):
        try:
            return joblib.load(p)
        except AttributeError as e:
            msg=str(e); last=msg
            m=re.search(r"Can't get attribute '([^']+)'", msg)
            if not m: raise
            name=m.group(1)
            if name not in globals():
                def _shim(X, *a, **k):
                    L=_ensure_list(X); return [ {} for _ in L ]
                _shim.__name__=name
                globals()[name]=_shim
                continue
            # 已存在同名還失敗，就別無限循環
            raise
    raise RuntimeError(f"Too many shim retries. Last error: {last}")

def read_jsonl(path):
    X, y = [], []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try:
                obj=json.loads(line)
            except Exception:
                X.append(line); y.append(None); continue
            txt = (obj.get('text') or obj.get('content') or obj.get('body') or
                   obj.get('email_text') or obj.get('message') or obj.get('q') or "")
            X.append("" if txt is None else str(txt))
            lab = (obj.get('label') if 'label' in obj else
                   obj.get('y') if 'y' in obj else
                   obj.get('intent_id') if 'intent_id' in obj else
                   obj.get('label_id') if 'label_id' in obj else
                   obj.get('intent') if 'intent' in obj else None)
            y.append(lab)
    return X, y

def eval_split(pipe, path, tag):
    X, y = read_jsonl(path)
    if hasattr(pipe, 'predict'):
        y_pred = pipe.predict(X)
    else:
        y_pred = [0]*len(X)
    # 計算有標註的樣本的準確率（盡量容錯型別）
    ok=0; tot=0
    for yi, yp in zip(y, y_pred):
        if yi is None: continue
        try:
            if isinstance(yi, str) and yi.isdigit(): yi = int(yi)
            if isinstance(yp, np.generic): yp = yp.item()
            if isinstance(yp, str) and yp.isdigit(): yp = int(yp)
            tot += 1
            ok  += int(yi == yp)
        except Exception:
            pass
    acc = (ok / tot) if tot>0 else 0.0
    print(f"[{tag}] n={len(X)} labeled={tot} acc={acc:.4f}")
    return {"n": len(X), "labeled": tot, "acc": acc}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--pipeline', default='artifacts_prod/model_pipeline.pkl')
    ap.add_argument('--test', default='data/intent/test.jsonl')
    ap.add_argument('--val',  default='data/intent/val.jsonl')
    ap.add_argument('--rules', default='artifacts_prod/intent_rules_calib.json')
    ap.add_argument('--thresholds', default='reports_auto/intent_thresholds.json')
    args=ap.parse_args()
    root=pathlib.Path(".")
    pipe = load_pipeline_with_auto_shims(root/args.pipeline)
    # 可用但不強依賴
    try: rules=json.load(open(root/args.rules,'r',encoding='utf-8')); rl=True
    except Exception: rl=False
    try: thr=json.load(open(root/args.thresholds,'r',encoding='utf-8')); tk=list(thr)[:5]
    except Exception: tk=[]
    out={}
    if pathlib.Path(args.test).exists(): out["test"]=eval_split(pipe, args.test, "TEST")
    if pathlib.Path(args.val).exists():  out["val"]= eval_split(pipe, args.val,  "VAL")
    out["rules_loaded"]=rl
    out["thr_keys"]=tk
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
