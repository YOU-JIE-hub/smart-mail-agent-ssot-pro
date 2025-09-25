import re, unicodedata, json
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix

RE_URL=re.compile(r"https?://[^\s)>\]]+",re.I)
SUS_TLD={".zip",".xyz",".top",".cam",".shop",".work",".loan",".country",".gq",".tk",".ml",".cf"}
SUS_EXT={".zip",".rar",".7z",".exe",".js",".vbs",".bat",".cmd",".htm",".html",".lnk",".iso",".docm",".xlsm",".pptm",".scr"}
KW=["重設密碼","驗證","帳戶異常","登入異常","補件","逾期","海關","匯款","退款","發票","稅務","罰款",
    "verify","reset","2fa","account","security","login","signin","update","confirm","invoice","payment","urgent","limited","verify your account"]

def _norm(s): return unicodedata.normalize("NFKC", (s or "")).lower()
def spam_signals(e):
    subj=_norm(e.get("subject","")); body=_norm(e.get("body","")); text=subj+" "+body
    sig=0
    urls=RE_URL.findall(text)
    if urls: sig+=1
    if any(u.lower().endswith(t) for u in urls for t in SUS_TLD): sig+=1
    if any(k in text for k in KW): sig+=1
    atts=[str(a).lower() for a in e.get("attachments",[]) if a]
    if any(a.endswith(ext) for a in atts for ext in SUS_EXT): sig+=1
    # 中英雙條件
    if ("account" in text) and (("verify" in text) or ("reset" in text) or ("login" in text) or ("signin" in text)): sig+=1
    if ("帳戶" in text)   and (("驗證" in text)  or ("重設" in text)  or ("登入" in text)): sig+=1
    return sig

def compute_metrics(y_true, y_pred):
    P,R,F1,_ = precision_recall_fscore_support(y_true,y_pred,average=None,labels=[0,1],zero_division=0)
    cm=confusion_matrix(y_true,y_pred,labels=[0,1]).tolist()
    return dict(macro=(F1[0]+F1[1])/2, hamP=P[0],hamR=R[0],hamF1=F1[0], spamP=P[1],spamR=R[1],spamF1=F1[1], cm=cm)

def dump_eval(path, tag, m, thr, sig_min, mode):
    with open(path,"w",encoding="utf-8") as w:
        w.write(f"[SPAM][EVAL] macro_f1={m['macro']:.4f} thr={thr:.2f} signals_min={sig_min} mode={mode}\n")
        w.write(f"[SPAM][EVAL] ham  P/R/F1 = {m['hamP']:.3f}/{m['hamR']:.3f}/{m['hamF1']:.3f}\n")
        w.write(f"[SPAM][EVAL] spam P/R/F1 = {m['spamP']:.3f}/{m['spamR']:.3f}/{m['spamF1']:.3f}\n")
        w.write(f"[SPAM][EVAL] confusion = {m['cm']}\n")
