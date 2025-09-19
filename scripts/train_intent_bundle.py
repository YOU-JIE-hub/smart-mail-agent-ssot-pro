# -*- coding: utf-8 -*-
import json, os, time, platform
from pathlib import Path
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.svm import LinearSVC
from sma_features.rules_v1 import RulesFeatV1
from scipy import sparse

DATA = Path(os.environ.get("INTENT_DATASET","data/intent_eval/dataset.cleaned.jsonl")).expanduser()
OUTROOT = Path("bundles/intent_v1"); OUTROOT.mkdir(parents=True, exist_ok=True)
TS = time.strftime("%Y%m%dT%H%M%S"); OUT = OUTROOT/TS; OUT.mkdir(parents=True, exist_ok=True)

def stream_jsonl(p):
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                o = json.loads(line); yield o.get("text",""), o.get("label","other")

X, y = zip(*list(stream_jsonl(DATA)))
labels = sorted(set(y))
word = TfidfVectorizer(ngram_range=(1,2), min_df=2, max_df=0.9)
char = TfidfVectorizer(analyzer="char", ngram_range=(3,5), min_df=2, max_df=0.9)
rules = RulesFeatV1()
features = FeatureUnion([("word", word), ("char", char), ("rules", rules)])
pipe = Pipeline([("features", features), ("clf", LinearSVC())])
pipe.fit(X, y)

# vocabs
(OUT/"vocab_word.txt").write_text("\n".join(word.vocabulary_.keys()), encoding="utf-8")
(OUT/"vocab_char.txt").write_text("\n".join(char.vocabulary_.keys()), encoding="utf-8")

bundle = {"pipeline": pipe, "label_order": labels, "feat_version": RulesFeatV1.VERSION}
joblib.dump(bundle, OUT/"pipeline.joblib", compress=3)

# 維度檢查與導出 manifest/schema
sample = "請幫我報價 120000 元，數量 3 台，單號 AB-99127"
Z = features.transform([sample])
assert sparse.isspmatrix(Z), "features.transform must return sparse matrix"
exp_total = Z.shape[1]; exp_word = len(word.vocabulary_); exp_char = len(char.vocabulary_); exp_rules = len(RulesFeatV1.FEATURES)
manifest = {
    "created_at": TS, "python": platform.python_version(),
    "sklearn": __import__("sklearn").__version__,
    "feat_impl": f"{RulesFeatV1.__module__}.{RulesFeatV1.__name__}",
    "feat_version": RulesFeatV1.VERSION,
    "dims": {"total": exp_total, "word": exp_word, "char": exp_char, "rules": exp_rules},
    "labels": labels, "dataset_path": str(DATA),
}
schema = {"rules":{"version":RulesFeatV1.VERSION,"features":RulesFeatV1.FEATURES},
          "word":{"vocab_size":exp_word,"ngram":[1,2]},
          "char":{"vocab_size":exp_char,"ngram":[3,5]}}
(OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2), encoding="utf-8")
(OUT/"feature_schema.json").write_text(json.dumps(schema,ensure_ascii=False,indent=2), encoding="utf-8")
(OUT/"sample_ping.txt").write_text(sample, encoding="utf-8")

# LATEST symlink
latest = OUTROOT/"LATEST"
try:
    if latest.exists() or latest.is_symlink(): latest.unlink()
except Exception: pass
latest.symlink_to(OUT.name)
print(f"[BUNDLE] {OUT}")
