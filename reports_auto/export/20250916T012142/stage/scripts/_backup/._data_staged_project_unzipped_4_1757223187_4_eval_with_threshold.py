#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, pickle
from pathlib import Path
import numpy as np
from rules_features import rules_feat

def is_pipeline(o):
    return hasattr(o, "predict") and (hasattr(o,"transform") or hasattr(o,"steps") or hasattr(o,"named_steps"))

def load_pipe(pkl: Path):
    obj = pickle.load(open(pkl, "rb"))
    if is_pipeline(obj): return obj
    if isinstance(obj, dict):
        for k in ("pipeline","sk_pipeline","pipe"):
            v = obj.get(k)
            if v is not None and is_pipeline(v): return v
    raise SystemExit(f"[FATAL] can't find pipeline in {pkl}")

def read_test(p: Path):
    X,Y,ids,langs=[],[],[],[]
    with open(p,"r",encoding="utf-8") as f:
        for ln in f:
            o = json.loads(ln)
            y = o.get("label") or o.get("intent") or o.get("y")
            t = o.get("text") or (o.get("subject","")+"\n"+o.get("body",""))
            if not t: t = json.dumps(o, ensure_ascii=False)
            X.append(t.strip()); Y.append(y or "")
            ids.append(o.get("id","")); langs.append(o.get("lang",""))
    return X,Y,ids,langs

def macro_f1(y_true, y_pred, labels):
    fs=[]
    for lab in labels:
        tp=fp=fn=0
        for yt,yp in zip(y_true,y_pred):
            tp += (yt==lab and yp==lab)
            fp += (yt!=lab and yp==lab)
            fn += (yt==lab and yp!=lab)
        P = tp/(tp+fp) if (tp+fp)>0 else 0.0
        R = tp/(tp+fn) if (tp+fn)>0 else 0.0
        F = (2*P*R/(P+R)) if (P+R)>0 else 0.0
        fs.append(F)
    return float(np.mean(fs)) if fs else 0.0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--test", required=True)
    ap.add_argument("--out_prefix", required=True)
    ap.add_argument("--p1", type=float, default=0.55, help="min top1 prob; else fallback to OTHER")
    ap.add_argument("--margin", type=float, default=0.12, help="min (p1-p2); else fallback to OTHER")
    ap.add_argument("--other_label", default="other")
    ap.add_argument("--only_tech", action="store_true", help="only allow fallback when original pred==tech_support")
    args = ap.parse_args()

    pipe = load_pipe(Path(args.model))
    X,Y,ids,langs = read_test(Path(args.test))

    # base prediction + probs
    y_base = pipe.predict(X)
    if hasattr(pipe, "predict_proba"):
        P = pipe.predict_proba(X)
    else:
        # very unlikely with CalibratedClassifierCV; provide safe fallback
        D = pipe.decision_function(X)
        D = np.atleast_2d(D)
        P = np.exp(D - D.max(axis=1, keepdims=True))
        P = P / P.sum(axis=1, keepdims=True)

    classes = getattr(getattr(pipe, "classes_", None), "tolist", lambda: None)()
    if classes is None:
        clf = getattr(pipe, "named_steps", {}).get("clf") or pipe
        classes = clf.classes_.tolist()

    # apply fallback
    y_new = []
    for i, (rowP, pred) in enumerate(zip(P, y_base)):
        order = np.argsort(-rowP)
        c1, c2 = order[0], (order[1] if len(order)>1 else order[0])
        p1, p2 = float(rowP[c1]), float(rowP[c2])
        margin = p1 - p2
        label1 = classes[c1]
        fallback = (p1 < args.p1) or (margin < args.margin)
        if args.only_tech:
            fallback = fallback and (pred == "tech_support")
        y_new.append(args.other_label if fallback else label1)

    labels = sorted(list(set(Y)))
    def dump_eval(prefix, y_pred):
        out_eval = Path(prefix+"_eval.txt")
        out_conf = Path(prefix+"_confusion.tsv")
        out_errs = Path(prefix+"_errors.tsv")

        acc = sum(yt==yp for yt,yp in zip(Y,y_pred))/len(Y)
        mac = macro_f1(Y, y_pred, labels)

        # confusion
        idx={lab:i for i,lab in enumerate(labels)}
        M=np.zeros((len(labels),len(labels)),dtype=int)
        for a,b in zip(Y,y_pred):
            if a in idx and b in idx: M[idx[a],idx[b]] += 1

        with open(out_eval,"w",encoding="utf-8") as fo:
            fo.write(f"pairs={len(Y)}\nAccuracy={acc:.4f}\nMacroF1={mac:.4f}\n")
            for lab in labels:
                tp=fp=fn=0
                for yt,yp in zip(Y,y_pred):
                    tp += (yt==lab and yp==lab)
                    fp += (yt!=lab and yp==lab)
                    fn += (yt==lab and yp!=lab)
                P = tp/(tp+fp) if (tp+fp)>0 else 0.0
                R = tp/(tp+fn) if (tp+fn)>0 else 0.0
                F = (2*P*R/(P+R)) if (P+R)>0 else 0.0
                fo.write(f"{lab}: P={P:.4f} R={R:.4f} F1={F:.4f} (tp={tp},fp={fp},fn={fn})\n")

        with open(out_conf,"w",encoding="utf-8") as fo:
            fo.write("label\t"+"\t".join(labels)+"\n")
            for i,lab in enumerate(labels):
                fo.write(lab+"\t"+"\t".join(str(int(x)) for x in M[i])+"\n")

        with open(out_errs,"w",encoding="utf-8") as fo:
            fo.write("id\tlang\tgold\tpred\ttext\n")
            for (txt,yt,idx_,lg),yp in zip(zip(X,Y,ids,langs), y_pred):
                if yt!=yp:
                    san=(txt or "").replace("\t"," ").replace("\n"," ")
                    fo.write(f"{idx_}\t{lg}\t{yt}\t{yp}\t{san[:500]}\n")
        return out_eval, out_conf, out_errs

    b1,b2,b3 = dump_eval(args.out_prefix+"_base", y_base)
    n1,n2,n3 = dump_eval(args.out_prefix, y_new)
    print("[OUT]", b1, b2, b3, "->", n1, n2, n3)

if __name__ == "__main__":
    main()
