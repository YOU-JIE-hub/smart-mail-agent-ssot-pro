
from __future__ import annotations
import sys, json, pathlib
from typing import Any
from tools.kie.hf_kie import decode

def _to_text(o: Any) -> str:
    if isinstance(o, str):
        return o
    if isinstance(o, dict):
        if "text" in o:
            return _to_text(o["text"])
        if "email" in o:
            return _to_text(o["email"])
        subj = o.get("subject") or o.get("title") or ""
        body = o.get("body") or o.get("content") or ""
        if subj or body:
            return f"{subj}\n{body}".strip()
        if "tokens" in o and isinstance(o["tokens"], list):
            return " ".join(map(str, o["tokens"]))
        # fallback：把所有子欄位的字串拼起來
        parts=[]
        for v in o.values():
            t=_to_text(v)
            if isinstance(t, str) and t:
                parts.append(t)
        return " ".join(parts)
    if isinstance(o, list):
        return " ".join([_to_text(x) for x in o])
    return ""

def main(inp: str, outp: str):
    pi=pathlib.Path(inp); po=pathlib.Path(outp)
    po.parent.mkdir(parents=True, exist_ok=True)
    with pi.open("r", encoding="utf-8") as f, po.open("w", encoding="utf-8") as g:
        for ln in f:
            if not ln.strip(): 
                continue
            try:
                obj=json.loads(ln)
            except Exception:
                obj={"text": ln.strip()}
            text=_to_text(obj).strip()
            if not text:
                continue
            spans=decode(text)  # 無 transformers 會自動走 regex-only
            g.write(json.dumps({"text": text, "spans": spans}, ensure_ascii=False)+"\n")

if __name__=="__main__":
    if len(sys.argv)<3:
        print("Usage: python tools/kie/eval.py <input.jsonl> <out.jsonl>", file=sys.stderr)
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
