from __future__ import annotations
from pathlib import Path
import os, json, re, time, math
from collections import Counter

OUT_DIR=Path(f"reports_auto/eval/{time.strftime('%Y%m%dT%H%M%S')}")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---- 資料探測 ----
CAND = [
    ("data/spam_sa/test.jsonl","data/spam_sa/val.jsonl"),
    ("data/spam/test.jsonl","data/spam/val.jsonl"),
    ("reports_auto/spam/test.jsonl","reports_auto/spam/val.jsonl"),
]
def pick_files():
    for t,v in CAND:
        if Path(t).exists() and Path(v).exists():
            return Path(t), Path(v)
    # 沒有就產最小集
    fx=Path("fixtures/spam_eval_set.jsonl"); fx.parent.mkdir(parents=True, exist_ok=True)
    if not fx.exists():
        fx.write_text("\n".join([
            json.dumps({"label":"ham","email":{"subject":"您好，訂單已出貨","body":"感謝您的訂購"}}),
            json.dumps({"label":"spam","email":{"subject":"免費中獎！點此領獎","body":"unsubscribe now"}}),
            json.dumps({"label":"spam","email":{"subject":"代刷評價只要$9.9","body":"限時優惠"}}),
            json.dumps({"label":"ham","email":{"subject":"會議通知","body":"附件為議程"}}),
        ]), encoding="utf-8")
    return fx, fx

TEST, VAL = pick_files()

# ---- ML 推論（若有權重）----
def _textify(e):
    if isinstance(e, dict):
        s=" ".join(str(e.get(k,"")) for k in ("subject","body","text"))
        return s.strip()
    return str(e)

def _ml_predict_many(emails):
    pkl=os.environ.get("SMA_SPAM_ML_PKL","")
    if not pkl:
        # 也允許 artifacts/spam*.pkl
        for cand in ["artifacts/spam_pro_cal.pkl","artifacts/spam_model.pkl","artifacts/spam.pkl"]:
            if Path(cand).exists(): pkl=cand; break
    if not pkl or not Path(pkl).exists(): return None
    try:
        from tools.ml_io import _alias_main_to_sma_features, _load_joblib, _unwrap_pipeline, _predict_raw
        _alias_main_to_sma_features()
        pipe=_unwrap_pipeline(_load_joblib(Path(pkl)))
        y=[]; 
        for e in emails:
            raw, conf = _predict_raw(pipe, _textify(e))
            # 正規化為 spam/ham
            lbl=str(raw).lower()
            if lbl in ("spam","1","true"): y.append(("spam",conf))
            elif lbl in ("ham","0","false","not_spam","clean"): y.append(("ham",conf))
            else:
                # 二元模型不明確時，信心值決策：>0.5 視為 spam
                y.append(("spam" if conf>=0.5 else "ham", conf))
        return y
    except Exception as e:
        return None

# ---- Rule baseline ----
SPAM_PAT = re.compile(r"(免費|中獎|點此|點擊|限時|優惠|代購|色|成人|貸款|借款|投資|虛擬幣|USDT|比特幣|unsubscribe|free|win|click|limited|offer|viagra|casino)", re.I)
def _rule_predict(e):
    txt=_textify(e)
    return "spam" if SPAM_PAT.search(txt) else "ham"

def _load_jsonl(p):
    L=[]
    for line in Path(p).read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        obj=json.loads(line)
        lab = str(obj.get("label") or obj.get("intent") or obj.get("y") or "").lower()
        if lab in ("1","true"): lab="spam"
        if lab in ("0","false"): lab="ham"
        email = obj.get("email") or {"subject":obj.get("subject",""), "body":obj.get("body","")}
        L.append((lab, email))
    return L

def eval_split(p):
    data=_load_jsonl(p)
    emails=[e for _,e in data]
    gold  =[g for g,_ in data]
    ml=_ml_predict_many(emails)
    if ml is None:
        pred=[_rule_predict(e) for e in emails]
        mode="rule"
    else:
        pred=[y for y,_ in ml]
        mode="ml"
    tp=fp=tn=fn=0
    for g,y in zip(gold,pred):
        if g=="spam" and y=="spam": tp+=1
        elif g=="spam" and y=="ham": fn+=1
        elif g=="ham"  and y=="spam": fp+=1
        elif g=="ham"  and y=="ham": tn+=1
    acc=(tp+tn)/max(1,len(gold))
    prec=tp/max(1,tp+fp)
    rec =tp/max(1,tp+fn)
    f1=0.0 if (prec+rec)==0 else 2*prec*rec/(prec+rec)
    return {"n":len(gold),"acc":acc,"prec":prec,"rec":rec,"f1":f1,"mode":mode,
            "cm":{"tp":tp,"fp":fp,"tn":tn,"fn":fn}}

rep={"test":eval_split(TEST),"val":eval_split(VAL)}
Path(OUT_DIR/"spam_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
Path(OUT_DIR/"spam_report.md").write_text(
    f"# spam eval\n- test n={rep['test']['n']} acc={rep['test']['acc']:.3f} f1={rep['test']['f1']:.3f} (mode={rep['test']['mode']})\n"
    f"- val  n={rep['val']['n']} acc={rep['val']['acc']:.3f} f1={rep['val']['f1']:.3f} (mode={rep['val']['mode']})\n",
    encoding="utf-8"
)
print(json.dumps(rep, ensure_ascii=False))
