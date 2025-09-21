#!/usr/bin/env python3
import os, sys, argparse
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.pipeline import Pipeline
import joblib

# --- 讓 joblib 能還原用 __main__ 存出的自訂類 ---
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
import importlib
tp = importlib.import_module("train_pro")
# 舊模型 pickle 可能記成 __main__.DictFeaturizer
sys.modules["__main__"].DictFeaturizer = tp.DictFeaturizer

# 與訓練相同的測試資料解析
from train_pro import parse_test  # -> texts, labels, ids, langs

def write_confusion(prefix, y_true, y_pred):
    labels = sorted(list({*y_true, *y_pred}))
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    with open(prefix + "_confusion.tsv", "w", encoding="utf-8") as f:
        f.write("label\t" + "\t".join(labels) + "\n")
        for i, row in enumerate(cm):
            f.write(labels[i] + "\t" + "\t".join(str(int(x)) for x in row) + "\n")

def write_errors(prefix, texts, ids, langs, y_true, y_pred, maxp):
    with open(prefix + "_errors.tsv", "w", encoding="utf-8") as f:
        f.write("id\tlang\tgold\tpred\tprob\ttext\n")
        for i, (yt, yp) in enumerate(zip(y_true, y_pred)):
            if yt != yp:
                san = texts[i].replace("\t", " ").replace("\n", " ")
                f.write(f"{ids[i]}\t{langs[i]}\t{yt}\t{yp}\t{maxp[i]:.3f}\t{san}\n")

def guard_to_other(txt: str) -> bool:
    """規則防呆：資訊索取/介紹但無明顯故障詞 -> other"""
    t = txt.lower()
    info_kw = ["api docs", "sdk", "integration", "roadmap", "case study", "deck", "video"]
    bad_kw  = ["error", "fail", "cannot", "timeout", "429", "5xx", "saml", "ntp"]
    return any(k in t for k in info_kw) and not any(k in t for k in bad_kw)

def build_pipe_from_model(model):
    """支援多種存檔格式：Pipeline、{'pipe': ...}、{'feats': ..., 'clf': ...}、{'model': ...}"""
    if isinstance(model, dict):
        if "pipe" in model:
            return model["pipe"]
        if "model" in model:
            return model["model"]
        if "feats" in model and "clf" in model:
            from sklearn.pipeline import Pipeline
            return Pipeline([("feats", model["feats"]), ("clf", model["clf"])])
        # 看起來像 dict 但沒有我們預期的鍵，幫忙丟出可診斷的錯誤
        raise KeyError(f"Unrecognized model dict keys: {list(model.keys())}")
    return model  # 不是 dict，當作已可預測的物件

def get_classes_from_pipe(pipe):
    if hasattr(pipe, "named_steps"):
        # 從最後一個 step 往回找有 classes_ 的分類器
        for name in reversed(list(pipe.named_steps.keys())):
            est = pipe.named_steps[name]
            if hasattr(est, "classes_"):
                return est.classes_
    if hasattr(pipe, "classes_"):
        return pipe.classes_
    raise ValueError("Cannot locate classes_ from pipeline/model")

def apply_fallback(texts, proba, classes, y_init, threshold, margin_min, only_tech=False, rules_guard=False):
    n = len(texts)
    y_top_idx = np.argmax(proba, axis=1)
    p1 = proba[np.arange(n), y_top_idx]
    p2 = np.partition(proba, -2, axis=1)[:, -2]
    margin = p1 - p2
    y_top = classes[y_top_idx].astype(object)

    # 規則防呆（先於 fallback）
    y_post = y_top.copy()
    guard_changed = 0
    if rules_guard:
        for i in range(n):
            if y_post[i] == "tech_support" and guard_to_other(texts[i]):
                y_post[i] = "other"
                guard_changed += 1

    # 低信心條件
    low_conf = (p1 < threshold) | (margin < margin_min)
    if only_tech:
        mask = (y_post == "tech_support") & low_conf
    else:
        mask = (y_post != "other") & low_conf

    y_fb = y_post.copy()
    y_fb[mask] = "other"
    changed = int(mask.sum())
    return y_fb, changed, guard_changed, p1, margin

def count_other_to_ts(y_true, y_pred):
    y_true = np.array(y_true); y_pred = np.array(y_pred)
    return int(np.sum((y_true == "other") & (y_pred == "tech_support")))

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
    ap.add_argument("--only-tech", action="store_true",
                    help="只對預測為 tech_support 的樣本啟用 fallback")
    ap.add_argument("--rules-guard", action="store_true",
                    help="啟用簡單關鍵詞防呆（TS→other）")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out_prefix), exist_ok=True)

    # 載入模型與資料
    model_raw = joblib.load(args.model)
    pipe = build_pipe_from_model(model_raw)
    texts, y_true, ids, langs = parse_test(args.test)

    # 基準預測
    y_base = pipe.predict(texts)
    proba = pipe.predict_proba(texts)
    classes = get_classes_from_pipe(pipe)

    # fallback
    y_fb, changed, guard_changed, p1, margin = apply_fallback(
        texts, proba, classes, y_base,
        threshold=args.threshold, margin_min=args.margin,
        only_tech=args.only_tech, rules_guard=args.rules_guard
    )

    # 指標與輸出
    base_acc = accuracy_score(y_true, y_base)
    fb_acc = accuracy_score(y_true, y_fb)
    o2ts_base = count_other_to_ts(y_true, y_base)
    o2ts_fb = count_other_to_ts(y_true, y_fb)

    with open(args.out_prefix + "_eval.txt", "w", encoding="utf-8") as f:
        f.write(f"[BASE]\taccuracy={base_acc:.3f}\n")
        f.write(classification_report(y_true, y_base, digits=3))
        f.write("\n\n")
        f.write(f"[FALLBACK] threshold={args.threshold} margin={args.margin} "
                f"only_tech={args.only_tech} rules_guard={args.rules_guard}\n")
        f.write(f"accuracy={fb_acc:.3f}\n")
        f.write(classification_report(y_true, y_fb, digits=3))
        f.write("\n")

    write_confusion(args.out_prefix, y_true, y_fb)
    write_errors(args.out_prefix, texts, ids, langs, y_true, y_fb, p1)

    print(f"[DONE] out={args.out_prefix}_*.txt/tsv")
    print(f"[ACC]  base={base_acc:.3f}  fallback={fb_acc:.3f}")
    print(f"[other->tech_support] {o2ts_fb}/{o2ts_base}  (after/before)")
    msg = f"[changed preds due to fallback] {changed}"
    if args.rules_guard:
        msg += f"  [rules-guard changed] {guard_changed}"
    print(msg)

    if args.scan:
        print("\n[SCAN]  thresh\tacc\t o->ts(after/before)\t changed")
        t = args.scan_start
        while t <= args.scan_end + 1e-9:
            y_tmp, chg, _, _, _ = apply_fallback(
                texts, proba, classes, y_base,
                threshold=t, margin_min=args.margin,
                only_tech=args.only_tech, rules_guard=args.rules_guard
            )
            acc = accuracy_score(y_true, y_tmp)
            o2ts_a = count_other_to_ts(y_true, y_tmp)
            print(f"\t{t:.2f}\t{acc:.3f}\t{o2ts_a}/{o2ts_base}\t\t{chg}")
            t = round(t + args.scan_step, 10)

if __name__ == "__main__":
    main()
