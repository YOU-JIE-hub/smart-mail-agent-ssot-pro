import os, json, pathlib
from pathlib import Path
import numpy as np, joblib
import matplotlib.pyplot as plt

# ##__CJK_FONT_HOOK__##
import matplotlib
from matplotlib import font_manager
from pathlib import Path as _P
def _install_cjk_fonts():
    roots = ["/usr/share/fonts","/usr/local/share/fonts",str(_P.home()/".fonts"),str(_P.home()/".local/share/fonts")]
    pats  = ["**/NotoSansCJK*.*","**/SourceHanSans*.*","**/Noto*Sans*CJK*.*"]
    loaded = 0
    for r in roots:
        pr = _P(r)
        if not pr.exists(): continue
        for pat in pats:
            for f in pr.glob(pat):
                try:
                    font_manager.fontManager.addfont(str(f))
                    loaded += 1
                except Exception:
                    pass
    try:
        # 重新建置快取，讓剛加的字型能被找到
        font_manager._load_fontmanager(try_read_cache=False)
    except Exception:
        pass
    matplotlib.rcParams['font.family'] = ['Noto Sans CJK SC','Noto Sans CJK TC','Noto Sans CJK JP','Source Han Sans','DejaVu Sans','sans-serif']
    matplotlib.rcParams['axes.unicode_minus'] = False
_install_cjk_fonts()


import matplotlib
# 字型 fallback：若系統有 Noto CJK 就用；沒有也不會中斷
matplotlib.rcParams['font.family'] = ['Noto Sans CJK JP','Noto Sans CJK TC','Noto Sans CJK SC','DejaVu Sans','Arial Unicode MS','sans-serif']
matplotlib.rcParams['axes.unicode_minus'] = False

from sklearn.metrics import confusion_matrix

root=Path("."); out=(root/"reports_auto/pro/latest"); out.mkdir(parents=True, exist_ok=True)

def read_jsonl(p):
    rows=[]
    for ln in Path(p).read_text("utf-8").splitlines():
        if ln.strip():
            try: rows.append(json.loads(ln))
            except: pass
    return rows

def predict_with_proba(m, X):
    y=m.predict(X)
    proba=None
    if hasattr(m,"predict_proba"):
        try: proba=m.predict_proba(X)
        except: proba=None
    elif hasattr(m,"decision_function"):
        try:
            df=m.decision_function(X)
            a=np.asarray(df)
            if a.ndim==1: a=np.vstack([-a, a]).T
            e=np.exp(a - a.max(axis=1, keepdims=True))
            proba=e/e.sum(axis=1, keepdims=True)
        except: proba=None
    return y, proba

def cm_plot(y_true, y_pred, labels, title, out_png):
    cm=confusion_matrix(y_true, y_pred, labels=labels)
    fig=plt.figure()
    ax=fig.add_subplot(111)
    im=ax.imshow(cm, interpolation='nearest')
    ax.set_title(title)
    ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels)
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, str(cm[i,j]), ha="center", va="center")
    ax.set_xlabel("Predicted"); ax.set_ylabel("True")
    fig.tight_layout(); fig.savefig(out_png, dpi=160); plt.close(fig)

def reliability_diagram(probs, y_true, out_png, n_bins=10):
    # probs: probability of positive class
    bins=np.linspace(0.0,1.0,n_bins+1)
    binids=np.digitize(probs, bins)-1
    acc=[]; conf=[]
    for b in range(n_bins):
        sel=(binids==b)
        if np.sum(sel)==0:
            acc.append(0.0); conf.append((bins[b]+bins[b+1])/2)
        else:
            acc.append(float(np.mean(y_true[sel])))
            conf.append(float(np.mean(probs[sel])))
    fig=plt.figure()
    ax=fig.add_subplot(111)
    ax.bar(np.arange(n_bins), acc, width=0.9, align='center')
    ax.plot(np.arange(n_bins), conf)
    ax.set_title("Spam Reliability (ECE visual aid)")
    ax.set_xlabel("Bin"); ax.set_ylabel("Empirical Accuracy / Mean Confidence")
    fig.tight_layout(); fig.savefig(out_png, dpi=160); plt.close(fig)

# Intent
pkl=os.environ.get("INTENT_PKL","")
if pkl and Path(pkl).exists():
    rows=read_jsonl(root/"data/intent_eval/test.jsonl")
    X=[r["text"] for r in rows]; y=[r["label"] for r in rows]
    m=joblib.load(pkl); yp,_=predict_with_proba(m,X)
    labels=list(getattr(m,"classes_", sorted(set(y))))
    cm_plot(y, yp, labels, "Intent Confusion Matrix", out/"cm_intent.png")

# Spam
pkl=os.environ.get("SPAM_PKL","")
if pkl and Path(pkl).exists():
    rows=read_jsonl(root/"data/spam_eval/test.jsonl")
    X=[r["text"] for r in rows]; y=np.array([int(r["label"]) for r in rows])
    m=joblib.load(pkl); yp,proba=predict_with_proba(m,X)
    labels=[0,1]; cm_plot(y, yp, labels, "Spam Confusion Matrix", out/"cm_spam.png")
    if proba is not None and proba.shape[1]>=2:
        reliability_diagram(proba[:,1], y, out/"reliability_spam.png")
print("[OK] charts:", out)
