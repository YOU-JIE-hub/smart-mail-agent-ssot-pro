import os, json, argparse, re, yaml, sys
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForTokenClassification
import torch

HERE = Path(__file__).parent
if str(HERE) not in sys.path: sys.path.insert(0, str(HERE))
from normalize_utils import norm_amount, norm_percent, norm_datetime, norm_duration, norm_env

def load_rules():
    return yaml.safe_load((HERE/"ruleset.yml").read_text(encoding="utf-8"))

def model_infer(mdir, texts):
    tok = AutoTokenizer.from_pretrained(mdir)
    mdl = AutoModelForTokenClassification.from_pretrained(mdir)
    mdl.eval(); out=[]
    for t in texts:
        enc = tok(t, return_offsets_mapping=True, truncation=True, max_length=512, return_tensors="pt")
        with torch.no_grad():
            logits = mdl(**{k:v for k,v in enc.items() if k in ("input_ids","attention_mask")}).logits[0]
        probs = torch.softmax(logits, dim=-1); ids = torch.argmax(probs, dim=-1).tolist()
        tags=[mdl.config.id2label[i] for i in ids]; offs = enc["offset_mapping"][0].tolist()
        spans=[]; cur=None
        for tag,(a,b) in zip(tags, offs):
            if a==b: continue
            if tag.startswith("B-"):
                if cur: spans.append(cur)
                cur={"label":tag[2:], "start":a, "end":b}
            elif tag.startswith("I-") and cur and cur["label"]==tag[2:]:
                cur["end"]=b
            else:
                if cur: spans.append(cur); cur=None
        if cur: spans.append(cur)
        out.append({"text":t, "spans":spans})
    return out

def rules_candidates(rules, text):
    cands=[]
    for field, cfg in rules.items():
        if field in ("version","currency_alias"): continue
        for p in (cfg or {}).get("patterns",[]):
            for m in re.finditer(p["regex"], text, flags=re.I):
                cands.append({"label":field, "start":m.start(), "end":m.end(), "raw":text[m.start():m.end()], **{k:v for k,v in p.items() if k!="regex"}})
    return cands

def normalize_field(label, raw):
    if label=="amount":
        ret = norm_amount(raw)
        if ret:
            v, ccy, _, scope = ret
            d={"value":v, "currency":ccy, "raw":raw}
            if scope: d["scope"]=scope
            return d
    if label in ("sla",):
        v = norm_percent(raw); return {"value":v or raw, "raw":raw}
    if label in ("rto","rpo"):
        v = norm_duration(raw); return {"value":v or raw, "raw":raw}
    if label in ("date_time",):
        v = norm_datetime(raw); return {"value":v or raw, "raw":raw}
    if label in ("env",):
        v = norm_env(raw); return {"value":v or raw}
    if label in ("http_status", "qps", "maus", "stores", "warehouses"):
        import re
        return {"value":re.sub(r'\D+','',raw) or raw, "raw":raw}
    if label in ("api_path","rate_limit","seats","po_grn","module"):
        return {"value":raw, "raw":raw}
    return {"value":raw, "raw":raw}

def fuse(rule_spans, ml_spans):
    merged = rule_spans[:]
    def iou(a,b):
        inter = max(0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
        union = max(a["end"], b["end"]) - min(a["start"], b["start"])
        return inter/union if union>0 else 0
    for m in ml_spans:
        if any((m["label"]==r["label"] and iou(m,r)>=0.6) for r in rule_spans):
            continue
        merged.append(m)
    return merged

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--model_dir", default="artifacts/kie_xlmr")
    ap.add_argument("--in_jsonl", required=True)
    ap.add_argument("--out_jsonl", default="reports_auto/kie_pred.jsonl")
    args=ap.parse_args()

    rules = load_rules()
    data = [json.loads(x) for x in Path(args.in_jsonl).read_text(encoding="utf-8").splitlines()]
    texts = [ (d.get("text") or (d.get("subject","")+"  "+d.get("body","")+"  "+d.get("content",""))).strip() for d in data ]
    ml_out = model_infer(args.model_dir, texts)

    with open(args.out_jsonl, "w", encoding="utf-8") as f:
        for d, p in zip(data, ml_out):
            rs = rules_candidates(rules, p["text"])
            spans = fuse(rs, p["spans"])
            fields={}
            for sp in spans:
                lab=sp["label"]; raw=p["text"][sp["start"]:sp["end"]]
                fields.setdefault(lab,[]).append(normalize_field(lab, raw))
            out={"id": d.get("id") or d.get("mid"), "lang": d.get("lang",""), "spans": spans, "fields": fields}
            f.write(json.dumps(out, ensure_ascii=False)+"\n")
    print(f"[DONE] {args.out_jsonl}")

if __name__=="__main__":
    main()
