#!/usr/bin/env python3
import re, sys, json, hashlib
def redact(t:str)->str:
    t=re.sub(r'[\w\.-]+@[\w\.-]+', '[EMAIL]', t)
    t=re.sub(r'\b(?:https?://|www\.)\S+', '[URL]', t)
    t=re.sub(r'\b(?:\+?\d[\d\-\s]{6,}\d)\b', '[PHONE]', t)
    t=re.sub(r'\b\d{1,3}(?:\.\d{1,3}){3}\b', '[IP]', t)
    # 常見人名/公司占位（粗略，避免傷到金額/日期/ENV）
    t=re.sub(r'公司[:：]?\s*\S+', '公司:[ORG]', t)
    t=re.sub(r'(?:敬上|Regards|Best),?\s*\S+$', 'Regards, [NAME]', t, flags=re.I|re.M)
    return t
def norm(s:str)->str:
    # 半形化（不動中文與幣值記號），保留 NT$ / USD / $ / ＄
    s=s.replace('，', ',').replace('．','.')
    return s
inp=sys.argv[1]; out=sys.argv[2]
with open(inp,encoding='utf-8') as fi, open(out,'w',encoding='utf-8') as fo:
    for ln in fi:
        o=json.loads(ln); t=o.get('text',''); o['text']=norm(redact(t))
        fo.write(json.dumps(o,ensure_ascii=False)+'\n')
print(f"[REDACT] -> {out}")
