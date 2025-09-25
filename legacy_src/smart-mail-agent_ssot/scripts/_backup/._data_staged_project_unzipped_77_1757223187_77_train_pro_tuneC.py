import os, argparse, itertools, json
from collections import Counter
from typing import List, Tuple
from train_pro import ( # 從既有檔案複用工具
    read_jsonl, join_subject_text, detect_lang, ensure_dir,
    load_xy, parse_test, build_pipeline
)
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.metrics import classification_report, confusion_matrix

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True)
    ap.add_argument("--test", required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--Cs", default="0.5,1.0,2.0")
    ap.add_argument("--out_prefix", default="reports_auto/tuneC")
    args = ap.parse_args()

    X_train, y_train = load_xy(args.train)
    X_test, y_test, ids, langs = parse_test(args.test)

    print(f"[TRAIN] n={len(X_train)} dist={Counter(y_train)}")
    print(f"[TEST]  n={len(X_test)}")

    Cs = [float(x) for x in args.Cs.split(",")]
    best = None
    rows = []
    for C in Cs:
        feats, _ = build_pipeline(seed=args.seed)
        base = LinearSVC(C=C, class_weight="balanced", random_state=args.seed)
        clf  = CalibratedClassifierCV(estimator=base, method="sigmoid", cv=3)
        pipe = Pipeline([("feats", feats), ("clf", clf)])
        pipe.fit(X_train, y_train)
        y_pred = pipe.predict(X_test)
        rep = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
        acc = rep["accuracy"]
        rows.append((C, acc, rep))
        if (best is None) or (acc > best[1]): best = (C, acc, rep)
        print(f"[C={C}] acc={acc:.3f}")

    C, acc, rep = best
    ensure_dir(args.out_prefix + "_best.txt")
    with open(args.out_prefix + "_best.txt", "w", encoding="utf-8") as f:
        f.write(f"best_C={C}\naccuracy={acc:.3f}\n")
        for k in sorted(rep.keys()):
            if isinstance(rep[k], dict) and "recall" in rep[k]:
                f.write(f"{k}\tP={rep[k]['precision']:.3f}\tR={rep[k]['recall']:.3f}\tF1={rep[k]['f1-score']:.3f}\n")
    print(f"[BEST] C={C} acc={acc:.3f} -> {args.out_prefix}_best.txt")
