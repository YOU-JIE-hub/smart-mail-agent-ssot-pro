import re, unicodedata
RE_URL=re.compile(r"https?://[^\s)>\]]+",re.I)
SUS_TLD={".zip",".xyz",".top",".cam",".shop",".work",".loan",".country",".gq",".tk",".ml",".cf"}
SUS_EXT={".zip",".rar",".7z",".exe",".js",".vbs",".bat",".cmd",".htm",".html",".lnk",".iso",".docm",".xlsm",".pptm",".scr"}
KW=["重設密碼","驗證","帳戶異常","登入異常","補件","逾期","海關","匯款","退款","發票","稅務","罰款",
    "verify","reset","2fa","account","security","login","signin","update","confirm","invoice","payment","urgent","limited","verify your account"]
def spam_signals_text(subj:str, body:str, atts:list[str]|None)->int:
    t=unicodedata.normalize("NFKC",((subj or "")+" "+(body or ""))).lower()
    urls=RE_URL.findall(t); A=[(a or "").lower() for a in (atts or []) if a]
    s=0
    if urls: s+=1
    if any(u.lower().endswith(tld) for u in urls for tld in SUS_TLD): s+=1
    if any(k in t for k in KW): s+=1
    if any(a.endswith(ext) for a in A for ext in SUS_EXT): s+=1
    if ("account" in t) and (("verify" in t) or ("reset" in t) or ("login" in t) or ("signin" in t)): s+=1
    if ("帳戶" in t) and (("驗證" in t) or ("重設" in t) or ("登入" in t)): s+=1
    return s
