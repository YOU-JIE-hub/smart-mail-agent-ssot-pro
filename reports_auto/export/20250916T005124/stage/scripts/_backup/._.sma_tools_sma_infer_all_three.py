#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from typing import Any, Dict, List

# --------- IO ---------
def read_jsonl(p: Path) -> List[Dict[str, Any]]:
    rows=[]
    with p.open('r', encoding='utf-8', errors='ignore') as f:
        for ln in f:
            if ln.strip():
                rows.append(json.loads(ln))
    return rows

def _json_default(o):
    try:
        import numpy as np
        if isinstance(o, (np.integer,)): return int(o)
        if isinstance(o, (np.floating,)): return float(o)
        if isinstance(o, (np.bool_,)): return bool(o)
        if isinstance(o, (np.ndarray,)): return o.tolist()
    except Exception:
        pass
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

def write_jsonl(p: Path, rows: List[Dict[str, Any]]) -> None:
    with p.open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=_json_default) + "\\n")

def text_of(e: Dict[str,Any]) -> str:
    s = (e.get("subject") or "").strip()
    b = (e.get("body") or e.get("text") or "").strip()
    return (s + "\\n" + b).strip()

# --------- 極簡穩定版 INTENT/SPAM（規則兜底，保證不閃退）---------
KW = {
  "biz_quote":      ("報價","報價單","估價","quote","quotation","estimate","pricing","price"),
  "tech_support":   ("錯誤","無法","壞掉","當機","crash","error","bug","exception","log","連不上","卡住","fail","issue"),
  "complaint":      ("抱怨","投訴","退費","不滿","差勁","延誤","拖延","沒人回","太慢","refund","bad","delay"),
  "policy_qa":      ("隱私","政策","條款","合約","dpa","gdpr","資安","法遵","合規","續約","nda","policy","contract"),
  "profile_update": ("變更","更新","修改","變更資料","帳號","密碼","email","電話","地址","profile","account"),
}
RE_URL = re.compile(r"https?://|\\.(zip|exe|js|vbs|bat|cmd|lnk|iso|docm|xlsm|pptm)\\b", re.I)

def intent_predict_rule(texts: List[str]):
    out=[]
    for t in texts:
        tl=(t or "").lower()
        scores = {k:0.0 for k in ("biz_quote","tech_support","complaint","policy_qa","profile_update","other")}
        for k in ("biz_quote","tech_support","complaint","policy_qa","profile_update"):
            if any(w in tl for w in KW[k]): scores[k]+=0.6
        if RE_URL.search(tl): scores["tech_support"]+=0.1
        c1 = max(scores, key=scores.get)
        c2 = "other" if c1!="other" else "tech_support"
        p1 = float(scores[c1]); p2 = float(scores.get(c2,0.0))
        tuned = c1 if p1>=0.5 else "other"
        out.append({"base_top1": c1, "base_top2": c2, "p1": p1, "p2": p2, "tuned": tuned})
    return out

def spam_predict_rule(texts: List[str]):
    preds=[]
    for t in texts:
        suspicious = 1 if RE_URL.search((t or "").lower()) else 0
        score = 0.7 if suspicious else 0.2
        pred_text = 1 if score >= 0.5 else 0
        pred_rule = suspicious
        pred_ens  = 1 if (pred_text or pred_rule) else 0
        preds.append({"score_text": float(score), "signals": 0, "pred_text": int(pred_text), "pred_rule": int(pred_rule), "pred_ens": int(pred_ens)})
    return preds

# --------- MAIN ---------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="input jsonl")
    ap.add_argument("--out", required=True, help="output jsonl")
    ap.add_argument("--id_field", default="id")
    args = ap.parse_args()

    src = Path(args.input)
    rows = read_jsonl(src)
    texts = [text_of(r) for r in rows]

    intent_out = intent_predict_rule(texts)
    spam_out   = spam_predict_rule(texts)

    out_rows=[]
    for i, (r, ip, sp) in enumerate(zip(rows, intent_out, spam_out)):
        rid = r.get(args.id_field, f"gen-{i+1:04d}")
        # numpy -> python + 字串化，防序列化炸掉
        try:
            import numpy as np
            if isinstance(rid, (np.integer,)): rid = int(rid)
            elif isinstance(rid, (np.floating,)): rid = float(rid)
            elif isinstance(rid, (np.bool_,)): rid = bool(rid)
        except Exception:
            pass
        rid = str(rid)
        out_rows.append({"id": rid, "intent": ip, "spam": sp, "kie": {"spans": []}})
    write_jsonl(Path(args.out), out_rows)

if __name__ == "__main__":
    main()
