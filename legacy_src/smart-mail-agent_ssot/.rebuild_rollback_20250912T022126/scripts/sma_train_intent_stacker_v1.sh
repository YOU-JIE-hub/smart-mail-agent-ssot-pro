#!/usr/bin/env bash
set -euo pipefail
cd /home/youjie/projects/smart-mail-agent_ssot
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1
TS="$(date +%Y%m%dT%H%M%S)"
EVADIR="reports_auto/eval/${TS}"
mkdir -p "$EVADIR" "artifacts_prod" "data/intent_eval"

python - <<'PY'
# -*- coding: utf-8 -*-
import json, time, joblib
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score, precision_recall_fscore_support

ROOT=Path("."); NOW=time.strftime("%Y%m%dT%H%M%S")
EVADIR=ROOT/f"reports_auto/eval/{NOW}"; EVADIR.mkdir(parents=True, exist_ok=True)
ds_p=None
for cand in [ROOT/"data/intent_eval/dataset.cleaned.jsonl", ROOT/"data/intent_eval/dataset.jsonl"]:
    if cand.exists() and cand.stat().st_size>0:
        ds_p=cand; break
assert ds_p, "dataset 不存在"
data=[json.loads(x) for x in ds_p.read_text("utf-8").splitlines() if x.strip()]
X=[d.get("text","") for d in data]
y=[d.get("label") or d.get("intent") for d in data]
# split
Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=0.2,random_state=42,stratify=y)
# vectorizer: char n-gram 3~5
vec=TfidfVectorizer(analyzer="char", ngram_range=(3,5), min_df=2, max_features=200000)
Xtrv=vec.fit_transform(Xtr)
Xtev=vec.transform(Xte)
# classifier
clf=LogisticRegression(max_iter=200, n_jobs=None, solver="saga", class_weight="balanced", multi_class="ovr")
clf.fit(Xtrv, ytr)
pred=clf.predict(Xtev)
p,r,f1,_=precision_recall_fscore_support(yte, pred, average="micro")
rep=classification_report(yte,pred,digits=3)
cm=confusion_matrix(yte,pred,labels=sorted(set(y)))
# save
joblib.dump({"vec":vec,"clf":clf,"labels":sorted(set(y))}, (ROOT/"artifacts_prod/intent_stacker_v1.pkl").as_posix())
md = ROOT/f"reports_auto/eval/{NOW}/intent_stacker_v1_metrics.md"
md.write_text(
    "# Intent Stacker v1 (char-gram + Logistic)\n"
    f"- dataset: {ds_p.as_posix()} size={len(X)}\n"
    f"- micro P/R/F1: {p:.3f}/{r:.3f}/{f1:.3f}\n\n"
    "## Classification report\n```\n"+rep+"\n```\n"
    "## Confusion matrix\n```\n"+str(cm)+"\n```\n", "utf-8"
)
print(f"[OK] saved model -> artifacts_prod/intent_stacker_v1.pkl")
print(f"[OK] metrics -> {md.as_posix()}")
PY
