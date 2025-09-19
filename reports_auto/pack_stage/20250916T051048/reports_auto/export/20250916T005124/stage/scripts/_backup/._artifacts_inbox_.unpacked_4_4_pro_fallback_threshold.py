#!/usr/bin/env python3
import os, sys, argparse
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.pipeline import Pipeline
import joblib

# 相容舊 pickle（__main__.DictFeaturizer）
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
import importlib
tp = importlib.import_module("train_pro")
sys.modules["__main__"].DictFeaturizer = tp.DictFeaturizer

from train_pro import parse_test  # -> texts, labels, ids, langs

def build_pipe(model_raw):
    if isinstance(model_raw, Pipeline):
        return model_raw
    if isinstance(model_raw, dict) and "feats" in model_raw and "clf" in model_raw:
        return Pipeline([("feats", model_raw["feats"]), ("clf", model_raw["clf"])])
    raise TypeError("Unsupported model object; expect sklearn Pipeline or {feats, clf} dict")

def guard_to_other(txt: str) -> bool:
    t = (txt or "").lower()
    # 需求/資料/簡介關鍵詞（英+中）
    info_kw = ["api docs","sdk","integration","roadmap","case study","deck","video",
               "api 文件","sdk","整合","路線圖","成功案例","簡報","影片","介紹","概覽"]
    # 故障/異常關鍵詞（英+中）
    bad_kw  = ["error","fail","failed","cannot","timeout","429","5xx","saml","ntp",
               "錯誤","失敗","無法","逾時","超時","429","5xx","saml","時鐘","不同步","限流","異常"]
    return any(k in t for k in info_kw) and not any(k in t for k in bad_kw)

def eval_and_write(prefix, y_true, y_pred, texts, ids, langs, proba, classes):
    # report
    rep_txt = classification_report(y_true, y_pred, digits=3)
    acc = accuracy_score(y_true, y_pred)
    with open(prefix + "_eval.txt","w",encoding="utf-8") as f:
        f.write(f"accuracy={acc:.3f}\n")
        f.write(rep_txt+"\n")

    # confusion
    labels = sorted(list({*y_true, *y_pred}))
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    with open(prefix + "_confusion.tsv","w",encoding="utf-8") as f:
        f.write("label\t" + "\t".join(labels) + "\n")
        for i, row in enumerate(cm):
            f.write(labels[i] + "\t" + "\t".join(str(int(x)) for x in row) + "\n")

    # errors
    with open(prefix + "_errors.tsv","w",encoding="utf-8") as f:
        f.write("id\tlang\tgold\tpred\tprob\ttext\n")
        for i,(yt,yp) in enumerate(zip(y_true,y_pred)):
            if yt!=yp:
                p_idx = np.where(classes==yp)[0][0] if yp in classes else np.argmax(proba[i])
                maxp = float(proba[i, p_idx]) if proba is not None else np.nan
                san = (texts[i] or "").replace("\t"," ").replace("\n"," ")
                f.write(f"{ids[i]}\t{langs[i]}\t{yt}\t{yp}\t{maxp:.3f}\t{san}\n")
    return acc

def apply_rules(y_pred, texts, only_tech=False):
    changed = 0
    y_post = y_pred.copy()
    for i in range(len(y_post)):
        if y_post[i]=="tech_support":
            if guard_to_other(texts[i]):
                y_post[i] = "other"; changed += 1
        elif not only_tech:
            # 如需擴展非 tech_support 的 guard，在此加入
            pass
    return y_post, changed

def apply_fallback(y_pred, proba, classes, threshold, margin, only_tech=False):
    y_post = y_pred.copy()
    y_idx = np.argmax(proba, axis=1)
    p1 = proba[np.arange(len(y_pred)), y_idx]
    p2 = np.partition(proba, -2, axis=1)[:, -2]
    low = (p1 < threshold) | ((p1 - p2) < margin)
    changed = 0
    for i in range(len(y_post)):
        if low[i] and ((not only_tech) or (y_post[i]=="tech_support")):
            y_post[i] = "other"; changed += 1
    return y_post, changed

def run(model_path, test_path, threshold, margin, out_prefix, scan=False, s0=0.50, s1=0.70, step=0.02, only_tech=False, rules_guard=False):
    texts, y_true, ids, langs = parse_test(test_path)
    model_raw = joblib.load(model_path)
    pipe = build_pipe(model_raw)
    proba = pipe.predict_proba(texts)
    classes = pipe.named_steps["clf"].classes_ if isinstance(pipe.named_steps.get("clf"), object) else np.array(sorted(list(set(y_true))))
    y_base = pipe.predict(texts)

    # 規則護欄
    y_guard = y_base
    guard_changed = 0
    if rules_guard:
        y_guard, guard_changed = apply_rules(y_base, texts, only_tech=only_tech)

    # fallback
    y_fb, fb_changed = apply_fallback(y_guard, proba, classes, threshold, margin, only_tech=only_tech)

    # 輸出
    base_acc = eval_and_write(out_prefix.replace("_fallback","")+"_fallback_base", y_true, y_base, texts, ids, langs, proba, classes)
    fb_acc   = eval_and_write(out_prefix, y_true, y_fb, texts, ids, langs, proba, classes)

    print(f"[DONE] out={out_prefix}_*.txt/tsv")
    print(f"[ACC]  base={base_acc:.3f}  fallback={fb_acc:.3f}")
    # 特別關注 other->tech_support 轉移
    def count_pair(y1,y2,a,b): return sum((p==a and q==b) for p,q in zip(y1,y2))
    o2ts_base = count_pair(y_true, y_base, "other","tech_support")
    o2ts_fb   = count_pair(y_true, y_fb,   "other","tech_support")
    print(f"[other->tech_support] {o2ts_fb}/{o2ts_base}  (after/before)")
    print(f"[changed preds due to fallback] {fb_changed}  [rules-guard changed] {guard_changed}")

    if scan:
        print("\n[SCAN]  thresh  acc      o->ts(after/before)     changed")
        t = s0
        while t <= (s1 + 1e-9):
            y_s, _ = apply_fallback(y_guard, proba, classes, t, margin, only_tech=only_tech)
            acc_s = accuracy_score(y_true, y_s)
            o2ts_s = count_pair(y_true, y_s, "other","tech_support")
            chg = sum(a!=b for a,b in zip(y_guard, y_s))
            print(f"        {t:.2f}    {acc_s:.3f}   {o2ts_s}/{o2ts_base}\t\t{chg}")
            t += step

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--test", required=True)
    ap.add_argument("--threshold", type=float, default=0.52)
    ap.add_argument("--margin", type=float, default=0.10)
    ap.add_argument("--out_prefix", default="reports_auto/external_fallback")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--scan-start", type=float, default=0.50)
    ap.add_argument("--scan-end", type=float, default=0.70)
    ap.add_argument("--scan-step", type=float, default=0.02)
    ap.add_argument("--only-tech", action="store_true", help="只針對預測為 tech_support 啟用 fallback")
    ap.add_argument("--rules-guard", action="store_true", help="啟用規則護欄（TS→other）")
    args = ap.parse_args()
    run(args.model, args.test, args.threshold, args.margin, args.out_prefix,
        scan=args.scan, s0=args["scan_start"] if hasattr(args,'__getitem__') else args.scan_start,
        s1=args.scan_end, step=args.scan_step, only_tech=args.only_tech, rules_guard=args.rules_guard)

if __name__ == "__main__":
    main()
