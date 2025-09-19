
import json, argparse, re
from pathlib import Path

def load_jsonl(fp):
    rows=[]
    with open(fp,'r',encoding='utf-8',errors='ignore') as f:
        for ln in f:
            if ln.strip(): rows.append(json.loads(ln))
    return rows

def save_jsonl(rows, fp):
    with open(fp,'w',encoding='utf-8') as w:
        for r in rows: w.write(json.dumps(r, ensure_ascii=False)+'\n')

def get_text(row):
    t = row.get('text')
    if not t: t = (row.get('subject','') + '\n' + row.get('body','')).strip()
    if not t: t = row.get('email','') or ''
    return t

def merge_nearby(spans, max_gap=1):
    if not spans: return spans
    spans = sorted(spans, key=lambda x:(x['start'], x['end']))
    out=[spans[0]]
    for s in spans[1:]:
        prev=out[-1]
        if s['label']==prev['label'] and s['start'] <= prev['end']+max_gap:
            prev['end'] = max(prev['end'], s['end'])
            if 'conf' in s and 'conf' in prev:
                prev['conf'] = max(prev['conf'], s['conf'])
        else:
            out.append(s)
    return out

# --- regex fallback (ASCII) ---
ENV_WORDS = re.compile(r"\b(?:uat|sit|stg|stage|pre[- ]?prod|preprod|prod|qa|dev|poc|sandbox|sbx|staging)\b", re.I)
SLA_WORDS = re.compile(r"\b(?:sla|sow|eow|eod|cob|deadline|due|eta)\b", re.I)

_CCY_LEFT  = r"(?:USD|TWD|NT\$|US\$|HK\$|CNY|EUR|GBP|JPY|AUD|CAD|SGD|NTD|\$|€|£|¥)"
_NUM_TAIL  = r"[\s]*[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,4})?"
AMT_REGEX  = re.compile(rf"(?:{_CCY_LEFT}\s*)?{_NUM_TAIL}(?:\s*(?:-\s*){_NUM_TAIL})?(?:\s*(?:USD|TWD|CNY|EUR|GBP|JPY|AUD|CAD|SGD))?", re.I)

MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)"
DATE1  = re.compile(r"\b(?:20\d{2}|19\d{2})[-/.](?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])(?:[ T](?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?)?\b")
DATE2  = re.compile(r"\b(?:0?[1-9]|[12]\d|3[01])[-/](?:0?[1-9]|1[0-2])[-/](?:\d{2,4})(?:\s+(?:[01]?\d|2[0-3]):[0-5]\d)?\b")
DATE3  = re.compile(rf"\b(?:[12]\d|3[01]|0?\d)\s+(?:{MONTHS})\.?\s+(?:20\d{{2}}|19\d{{2}})\b", re.I)

def expand_amount(text, s, e):
    L, R = max(0,int(s)), min(len(text), int(e))
    l0 = max(0, L-16); r0 = min(len(text), R+64)
    left  = text[l0:L]; right = text[R:r0]
    m_right = re.match(_NUM_TAIL + r"(?:\s*%|\s*(?:USD|TWD|CNY|EUR|GBP|JPY|AUD|CAD|SGD))?", right, re.I)
    if m_right: R = R + m_right.end()
    m_left  = re.search(r"(?:\(|" + _CCY_LEFT + r")$", left, re.I)
    if m_left: L = l0 + m_left.start()
    if R < len(text) and text[R:R+1] == ")": R += 1
    return max(0,L), min(len(text),R)

def regex_fallback(text):
    spans=[]
    for m in AMT_REGEX.finditer(text):
        l, r = expand_amount(text, m.start(), m.end())
        if r>l: spans.append({'start':l,'end':r,'label':'amount','conf':0.0})
    for rx in (DATE1, DATE2, DATE3):
        for m in rx.finditer(text):
            spans.append({'start':m.start(),'end':m.end(),'label':'date_time','conf':0.0})
    for m in ENV_WORDS.finditer(text):
        spans.append({'start':m.start(),'end':m.end(),'label':'env','conf':0.0})
    for m in SLA_WORDS.finditer(text):
        spans.append({'start':m.start(),'end':m.end(),'label':'sla','conf':0.0})
    return merge_nearby(spans, max_gap=1)

def run_kie(texts, kie_dir, chunk=8, max_len=512, min_prob=0.55, fallback_mode='empty'):
    from transformers import AutoTokenizer, AutoModelForTokenClassification
    import torch, math
    tok = AutoTokenizer.from_pretrained(kie_dir)
    mdl = AutoModelForTokenClassification.from_pretrained(kie_dir)
    mdl.eval(); mdl.to('cpu')

    id2label = getattr(mdl.config, 'id2label', None)
    if isinstance(id2label, dict) and len(id2label)>0:
        labels = [ id2label.get(i) or id2label.get(str(i)) or str(i) for i in range(mdl.config.num_labels) ]
    else:
        labels = [ str(i) for i in range(mdl.config.num_labels) ]

    def base_label(x):
        if not x or x=='O': return 'O'
        x=str(x)
        if '-' in x: x=x.split('-',1)[1]
        return x.lower()

    outs=[]
    with torch.no_grad():
        for i in range(0, len(texts), max(1,int(chunk))):
            batch = texts[i:i+chunk]
            enc = tok(batch, return_offsets_mapping=True, truncation=True, max_length=max_len, return_tensors='pt', padding=True)
            offs = enc.pop('offset_mapping')
            logits = mdl(**enc).logits  # [B, T, C]
            probs = torch.softmax(logits, dim=-1)
            pred  = probs.argmax(-1)

            for b_idx, t in enumerate(batch):
                off = offs[b_idx].tolist()
                pv  = probs[b_idx].tolist()
                ids = pred[b_idx].tolist()

                spans=[]; cur=None; cur_conf_sum=0.0; cur_conf_cnt=0
                for (st,ed), lbl_idx, probvec in zip(off, ids, pv):
                    bl = base_label(labels[lbl_idx])
                    conf = float(max(probvec))  # token confidence
                    if bl=='o' or (st==ed):
                        if cur is not None:
                            # close span
                            avg_conf = cur_conf_sum / max(1,cur_conf_cnt)
                            if avg_conf >= min_prob:
                                cur['conf'] = avg_conf
                                spans.append(cur)
                            cur=None; cur_conf_sum=0.0; cur_conf_cnt=0
                    else:
                        if cur is None or cur['label']!=bl or st>cur['end']:
                            if cur is not None:
                                avg_conf = cur_conf_sum / max(1,cur_conf_cnt)
                                if avg_conf >= min_prob:
                                    cur['conf'] = avg_conf
                                    spans.append(cur)
                            cur={'start':st,'end':ed,'label':bl}; cur_conf_sum=conf; cur_conf_cnt=1
                        else:
                            cur['end']=max(cur['end'], ed)
                            cur_conf_sum += conf; cur_conf_cnt += 1
                if cur is not None:
                    avg_conf = cur_conf_sum / max(1,cur_conf_cnt)
                    if avg_conf >= min_prob:
                        cur['conf'] = avg_conf
                        spans.append(cur)

                # fallback 策略
                fb = regex_fallback(t)
                if fallback_mode=='union':
                    spans = merge_nearby((spans or []) + fb, max_gap=1)
                elif fallback_mode=='empty' and not spans:
                    spans = fb
                # else 'off': do nothing

                for s in spans:
                    s['text'] = t[s['start']:s['end']]
                outs.append(spans)
    return outs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--pred_in', required=True)
    ap.add_argument('--pred_out', required=True)
    ap.add_argument('--kie_dir', required=True)
    ap.add_argument('--chunk', type=int, default=8)
    ap.add_argument('--maxlen', type=int, default=512)
    ap.add_argument('--min_prob', type=float, default=0.55)
    ap.add_argument('--fallback_mode', choices=['union','empty','off'], default='empty')
    ap.add_argument('--keep_labels', default='')
    args = ap.parse_args()

    src_rows  = load_jsonl(args.src)
    pred_rows = load_jsonl(args.pred_in)
    by_id = {r.get('id',i):i for i,r in enumerate(pred_rows)}

    texts = [ get_text(r) for r in src_rows ]
    k_spans = run_kie(texts, args.kie_dir, chunk=args.chunk, max_len=args.maxlen,
                      min_prob=args.min_prob, fallback_mode=args.fallback_mode)

    keep = set([x.strip().lower() for x in args.keep_labels.split(',') if x.strip()]) if args.keep_labels else None

    updated=0
    for src, spans in zip(src_rows, k_spans):
        if keep: spans = [s for s in spans if s.get('label','').lower() in keep]
        rid = src.get('id'); idx = by_id.get(rid, None)
        if idx is None: continue
        rec = pred_rows[idx]
        rec.setdefault('kie', {})['spans'] = spans
        updated+=1

    save_jsonl(pred_rows, args.pred_out)
    print(f"[DONE] wrote {args.pred_out}  n={len(pred_rows)}  kie_updated={updated}")
if __name__ == '__main__':
    main()
