
from __future__ import annotations
import os, re
from pathlib import Path
from typing import List, Dict, Any

# 盡力載入 HF；若失敗 → Regex-only
HAS_HF = True  # fallback to regex-only on load failure
try:
    from transformers import AutoTokenizer, AutoModelForTokenClassification  # type: ignore
    import torch  # type: ignore
except Exception:
    HAS_HF = False

# 共用規則（與先前版一致，並補 qty/ticket）
_PATS: Dict[str, list[re.Pattern]] = {
    "amount": [
        re.compile(r"(?:NT\$|US\$|\$|＄)\s?[0-9０-９][0-9０-９,，]*(?:[\.．][0-9０-９]+)?", re.I)
    ],
    "date_time": [
        re.compile(r"\b[12][0-9]{3}[./-][0-9]{1,2}[./-][0-9]{1,2}\b"),
        re.compile(r"\b[0-9]{1,2}/[0-9]{1,2}\b")
    ],
    "env": [
        re.compile(r"\b(prod|production|prd|staging|stage|stg|uat|test|dev)\b", re.I)
    ],
    "sla": [
        re.compile(r"\b(SLA|RTO|RPO|EOD|EOW)\b", re.I)
    ],
    # 這兩個是你專題會用到的補槽位
    "qty": [
        re.compile(r"\b(?:qty|數量)[\s:=\-]*([0-9]+)\b", re.I),
    ],
    "ticket": [
        re.compile(r"\b(?:ticket|ts|單號)[:\- ]?([A-Z]{2,5}-?[0-9]{3,8})\b"),
    ],
}

_tok = None
_mdl = None
_id2label: Dict[int,str] | None = None

def _resolve_model_dir() -> Path:
    env = os.environ.get("KIE_MODEL_DIR", "").strip()
    cands = ([Path(env)] if env else []) + [Path("artifacts_inbox/kie1/model"), Path("model")]
    for p in cands:
        if p.exists() and (p / "config.json").exists():
            return p
    raise FileNotFoundError("KIE model dir not found. Set KIE_MODEL_DIR or place HF files in artifacts_inbox/kie1/model 或 model/")

def _ensure_hf():
    global _tok, _mdl, _id2label
    if not HAS_HF:
        return
    if _tok is None or _mdl is None:
        mdir = _resolve_model_dir()
        _tok = AutoTokenizer.from_pretrained(mdir, use_fast=True)
        _mdl = AutoModelForTokenClassification.from_pretrained(mdir)
        _mdl.eval()
        try:
            import torch  # noqa: F401
            torch.set_grad_enabled(False)  # type: ignore
        except Exception:
            pass
        _id2label = _mdl.config.id2label  # type: ignore

def _decode_regex_only(text:str) -> List[Dict[str,Any]]:
    spans = []
    for lab, rxs in _PATS.items():
        for rx in rxs:
            for m in rx.finditer(text):
                a, b = m.start(), m.end()
                spans.append({"start": a, "end": b, "label": lab})
    # 去重：同起訖同標籤唯一
    seen = set(); out=[]
    for s in sorted(spans, key=lambda x: (x["start"], x["end"], x["label"])):
        k=(s["start"], s["end"], s["label"])
        if k in seen: continue
        seen.add(k); out.append(s)
    return out

def decode(text: str) -> List[Dict[str, Any]]:
    if not HAS_HF:
        # 沒 transformers → 直接 regex-only
        return _decode_regex_only(text)

    # HF 正常 → 跑序列標註 + snapping
    _ensure_hf()
    assert _tok is not None and _mdl is not None and _id2label is not None
    enc = _tok(text, return_offsets_mapping=True, truncation=True, max_length=384, return_tensors="pt")  # type: ignore
    offs = enc.pop("offset_mapping")[0].tolist()  # type: ignore
    logits = _mdl(**{k: v for k, v in enc.items()}).logits[0]  # type: ignore
    pred_ids = logits.argmax(-1).tolist()

    spans = []
    cur = None
    for i, (a, b) in enumerate(offs):
        if a == b: 
            continue
        lab = _id2label.get(pred_ids[i], "O")  # type: ignore
        if lab.startswith("B-"):
            if cur: spans.append(cur); cur=None
            cur = {"start": a, "end": b, "label": lab[2:]}
        elif lab.startswith("I-") and cur and cur["label"] == lab[2:]:
            cur["end"] = b
        else:
            if cur: spans.append(cur); cur=None
    if cur: spans.append(cur)

    # snapping 規則
    snapped = []
    for s in spans:
        label = s["label"]
        patt_list = _PATS.get(label.lower(), [])
        best = None; ov_best = 0
        for rx in patt_list:
            for m in rx.finditer(text):
                a, b = m.start(), m.end()
                ov = max(0, min(s["end"], b) - max(s["start"], a))
                if ov > ov_best:
                    ov_best = ov; best = (a, b)
        if best:
            s["start"], s["end"] = best
        snapped.append(s)

    # 去重
    uniq = set(); out=[]
    for s in sorted(snapped, key=lambda x: (x["start"], x["end"], x["label"])):
        t=(s["start"], s["end"], s["label"])
        if t in uniq: 
            continue
        uniq.add(t); out.append(s)
    return out
