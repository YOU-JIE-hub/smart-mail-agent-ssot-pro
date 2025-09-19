#!/usr/bin/env python3
import argparse, json, math, statistics as st, sys

def sigmoid(x):
    try:
        return 1.0 / (1.0 + math.exp(-float(x)))
    except Exception:
        return None

def as_float(x):
    try:
        v = float(x)
        if math.isfinite(v):
            return v
    except Exception:
        pass
    return None

def clip01(x):
    if x is None: return 0.0
    if x < 0.0:   return 0.0
    if x > 1.0:   return 1.0
    return x

def infer_score(sp):
    # 1) 已有合理 score_text
    v = as_float(sp.get("score_text"))
    if v is not None and 0.0 <= v <= 1.0:
        return v, "keep"

    # 2) 常見 key：單值機率
    for k in ("proba_spam","prob_spam","p_spam","spam_prob","spam_proba",
              "p1","pos_proba","spam_score","score_prob"):
        v = as_float(sp.get(k))
        if v is not None:
            return clip01(v), k

    # 3) proba 容器
    proba = sp.get("proba")
    if isinstance(proba, dict):
        for k in ("spam","1","pos","true","label_1"):
            v = as_float(proba.get(k))
            if v is not None:
                return clip01(v), f"proba[{k}]"
    if isinstance(proba, (list, tuple)) and len(proba) == 2:
        v = as_float(proba[1])  # assume [ham, spam]
        if v is not None:
            return clip01(v), "proba[idx1]"

    # 4) margin/logit/decision → sigmoid
    for k in ("decision","decision_function","margin","logit","raw","score_raw"):
        v = as_float(sp.get(k))
        if v is not None:
            s = sigmoid(v)
            if s is not None:
                return clip01(s), f"sigmoid({k})"

    # 5) 只有 label
    lab = str(sp.get("label","")).strip().lower()
    if lab in ("spam","1","true"):
        return 1.0, "from_label"
    if lab in ("ham","0","false"):
        return 0.0, "from_label"

    return None, "unknown"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i","--in",  dest="inp",  required=True)
    ap.add_argument("-o","--out", dest="outp", required=True)
    ap.add_argument("--force", action="store_true",
                    help="無論是否已有 score_text 都重算")
    a = ap.parse_args()

    n=upd=kept=miss=0
    sources={}
    with open(a.outp, "w", encoding="utf-8") as g:
        for ln in open(a.inp, encoding="utf-8", errors="ignore"):
            if not ln.strip():
                g.write(ln); continue
            o = json.loads(ln); n += 1
            sp = (o.get("spam") or {})
            if not isinstance(sp, dict):
                o["spam"] = sp = {}

            score, src = infer_score(sp)

            rewrite = a.force or (sp.get("score_text") in (None, "",))
            if rewrite and score is not None:
                sp["score_text"] = float(score)
                upd += 1
                sources[src] = sources.get(src, 0) + 1
            elif rewrite:
                miss += 1
            else:
                kept += 1

            g.write(json.dumps(o, ensure_ascii=False) + "\n")

    # 簡報
    scores=[]
    for ln in open(a.outp, encoding="utf-8", errors="ignore"):
        if not ln.strip(): continue
        sp=(json.loads(ln).get("spam") or {})
        v=as_float(sp.get("score_text"))
        if v is not None: scores.append(v)
    mean = (st.mean(scores) if scores else None)
    ge05 = sum(1 for v in scores if v>=0.5)
    print(f"[FIX] n={n} updated={upd} kept={kept} miss={miss} "
          f"mean={mean}  >=0.5={ge05}/{len(scores)}  sources={sources}")

if __name__ == "__main__":
    main()
