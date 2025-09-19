import json, argparse, re, sys
from pathlib import Path
from seqeval.metrics import precision_score, recall_score, f1_score

HERE = Path(__file__).parent
if str(HERE) not in sys.path: sys.path.insert(0, str(HERE))
from normalize_utils import norm_amount, norm_datetime, norm_duration, norm_env

def load_jsonl(p): return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines()]

def seqeval_from_spans(text, spans):
    toks=list(text); tags=["O"]*len(toks)
    for sp in spans:
        s,e,lab=sp["start"],sp["end"],sp["label"]; 
        for i in range(s,e): tags[i] = ("B-" if i==s else "I-")+lab
    return toks, tags

def strict_f1(golds, preds):
    gt_tags, pd_tags = [], []
    for g,p in zip(golds, preds):
        _, gtags = seqeval_from_spans(g["text"], g.get("labels",[]))
        _, ptags = seqeval_from_spans(g["text"], p.get("spans",[]))
        gt_tags.append(gtags); pd_tags.append(ptags)
    return {"precision": precision_score(gt_tags, pd_tags), "recall": recall_score(gt_tags, pd_tags), "f1": f1_score(gt_tags, pd_tags)}

def value_eq(label, graw, praw):
    if label=="amount":
        g = norm_amount(graw); p = norm_amount(praw); return bool(g and p and g[0]==p[0] and (g[1] or "")==(p[1] or ""))
    if label in ("rto","rpo"): return norm_duration(graw)==norm_duration(praw) and norm_duration(graw) is not None
    if label=="date_time": return norm_datetime(graw)==norm_datetime(praw) and norm_datetime(graw) is not None
    if label=="env": return norm_env(graw)==norm_env(praw) and norm_env(graw) is not None
    return graw.strip()==praw.strip()

def value_accuracy(golds, preds, labels=("amount","date_time","rto","rpo","env","sla")):
    ok=tot=0
    for g,p in zip(golds, preds):
        gmap={}; pmap={}
        for s in g.get("labels",[]): gmap.setdefault(s["label"], []).append(s.get("raw") or g["text"][s["start"]:s["end"]])
        for s in p.get("spans",[]): pmap.setdefault(s["label"], []).append(s.get("raw") or p["text"][s["start"]:s["end"]])
        for lab in labels:
            if lab in gmap:
                tot += 1
                if lab in pmap and any(value_eq(lab, graw, praw) for graw in gmap[lab] for praw in pmap[lab]): ok += 1
    return ok, tot, (ok/tot if tot else 0.0)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--gold_jsonl", required=True)
    ap.add_argument("--pred_jsonl", required=True)
    args=ap.parse_args()

    gold=load_jsonl(args.gold_jsonl); pred=load_jsonl(args.pred_jsonl)
    m=strict_f1(gold, pred)
    ok, tot, acc=value_accuracy(gold, pred)
    print(f"[ENTITY] P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f}")
    print(f"[VALUE ] acc={acc:.3f} ({ok}/{tot})")

if __name__=="__main__":
    main()
