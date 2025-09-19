import os, re
from pathlib import Path
try:
    from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
    _TRANS = True
except Exception:
    _TRANS = False

ROOT = Path(os.getenv("SMA_ROOT", "/home/youjie/projects/smart-mail-agent_ssot"))
KIE_DIR = ROOT/"kie"
_LABEL_MAP = {
    "B-date_time":"date_time","I-date_time":"date_time",
    "B-amount":"amount","I-amount":"amount",
    "B-env":"env","I-env":"env",
    "B-sla":"sla","I-sla":"sla",
}

_nlp = None
def _load():
    global _nlp
    if os.getenv("KIE_DISABLE","0")=="1" or not _TRANS:
        _nlp = None; return
    tok = AutoTokenizer.from_pretrained(str(KIE_DIR), local_files_only=True)
    mdl = AutoModelForTokenClassification.from_pretrained(str(KIE_DIR), local_files_only=True)
    _nlp = pipeline("token-classification", model=mdl, tokenizer=tok, aggregation_strategy="simple")

def _regex_fallback(text):
    spans=[]
    m = re.search(r"(20\\d{2}[-/\\.](0?[1-9]|1[0-2])[-/\\.](0?[1-9]|[12]\\d|3[01]))", text)
    if m: spans.append(("date_time", m.group(1), m.start(), m.end()))
    m = re.search(r"(NTD|NT\\$|\\$)\\s?([0-9]{1,3}(,[0-9]{3})*(\\.[0-9]+)?|[0-9]+(\\.[0-9]+)?)", text)
    if m: spans.append(("amount", m.group(0), m.start(), m.end()))
    for env in ["prod","staging","dev","UAT","uat"]:
        i=text.lower().find(env.lower())
        if i>=0: spans.append(("env", env, i, i+len(env)))
    m = re.search(r"(\\d+)\\s*(hours|hrs|days|天|小時)", text, re.I)
    if m: spans.append(("sla", m.group(0), m.start(), m.end()))
    return spans

def extract(text: str):
    if _nlp is None:
        try: _load()
        except Exception: _nlp=None
    if _nlp is None: return _regex_fallback(text)
    outs = _nlp(text)
    spans=[]
    for o in outs:
        lab = _LABEL_MAP.get(o["entity_group"], o["entity_group"])
        if lab in {"date_time","amount","env","sla"}:
            start, end = int(o["start"]), int(o["end"])
            spans.append((lab, text[start:end], start, end))
    return spans
