import os, json, pathlib, re, random, joblib
from pathlib import Path
from sklearn.metrics import accuracy_score, f1_score

root=Path("."); out=(root/"reports_auto/pro/latest"); out.mkdir(parents=True, exist_ok=True)

def read_jsonl(p):
    p=Path(p); rows=[]
    if p.exists():
        for ln in p.read_text("utf-8").splitlines():
            ln=ln.strip()
            if ln:
                try: rows.append(json.loads(ln))
                except: pass
    return rows

def perturbations(s):
    outs=[s]
    outs.append(s.upper())
    outs.append(s.lower())
    outs.append(re.sub(r"[^\w\u4e00-\u9fff]+"," ", s))
    outs.append("👉 "+s+" 😊")
    outs.append(s + " http://example.com")
    outs.append(re.sub(r"\s+","  ", s))
    return outs[:6]

def eval_robust(name, model_env, data_path, label_key="label"):
    pkl=os.environ.get(model_env,"")
    rows=read_jsonl(data_path)
    X=[r.get("text","") for r in rows]
    y=[r.get(label_key,0) for r in rows]
    if name=="spam": y=[int(v) for v in y]
    res={"task":name,"n":len(X),"baseline":{},"shifts":[]}
    if not pkl or not Path(pkl).exists() or not X:
        res["status"]="skip"; return res
    m=joblib.load(pkl)
    y_pred=m.predict(X)
    res["baseline"]={"accuracy": float(accuracy_score(y,y_pred)),
                     "macro_f1": float(f1_score(y,y_pred,average="macro",zero_division=0))}
    # 採樣子集做擾動（最多 64 筆避免爆量）
    idx=list(range(len(X)))[:min(64,len(X))]
    for kind in ["upper","lower","strip_punct","emoji","url","double_space"]:
        Xp=[]
        for i in idx:
            txt=X[i]
            if kind=="upper": Xp.append(txt.upper())
            elif kind=="lower": Xp.append(txt.lower())
            elif kind=="strip_punct": 
                Xp.append(re.sub(r"[^\w\u4e00-\u9fff]+"," ", txt))
            elif kind=="emoji": Xp.append("👉 "+txt+" 😊")
            elif kind=="url": Xp.append(txt+" http://example.com")
            elif kind=="double_space": Xp.append(re.sub(r"\s+","  ", txt))
        yp=m.predict(Xp)
        res["shifts"].append({"kind":kind,
                              "n":len(Xp),
                              "accuracy": float(accuracy_score([y[i] for i in idx], yp)),
                              "macro_f1": float(f1_score([y[i] for i in idx], yp, average="macro", zero_division=0))})
    res["status"]="ok"; return res

out_json={"intent": eval_robust("intent","INTENT_PKL", root/"data/intent_eval/test.jsonl", "label"),
          "spam":   eval_robust("spam","SPAM_PKL", root/"data/spam_eval/test.jsonl", "label")}
(out/"robustness.json").write_text(json.dumps(out_json, ensure_ascii=False, indent=2), "utf-8")
print("[OK] wrote", out/"robustness.json")
