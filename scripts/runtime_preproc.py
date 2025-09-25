import re
_ZW = re.compile(r'[\u200B-\u200D\uFEFF]')
_URL= re.compile(r'https?://\S+|www\.\S+', re.I)
_WS = re.compile(r'\s+')
def normalize_text(s: str) -> str:
    if not isinstance(s,str): s=str(s)
    s = s.replace('\r\n','\n')
    s = _ZW.sub('', s)
    s = _URL.sub('<URL>', s)
    s = _WS.sub(' ', s).strip()
    return s
