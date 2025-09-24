from typing import List
import re
SYMBOLS = set("~!@#$%^&*()_+-=[]{}/\\|;:'\",.<>?，。！？；：「」『』（）《》【】、．—")
def rules_feat(texts: List[str]):
    import numpy as np
    feats=[]
    for t in texts:
        s = t or ""
        f_api   = int("api" in s.lower() or "接口" in s or "串接" in s)
        f_policy= int(("退" in s and "規" in s) or ("policy" in s.lower()))
        f_error = int(any(k in s.lower() for k in ["error","exception","錯誤","壞掉","當機"]))
        f_price = int(any(k in s for k in ["報價","價格","費用","價錢","quote","price"]))
        f_prof  = int(any(k in s for k in ["地址","電話","姓名","email","變更","更新","修改"]))
        f_digit = int(bool(re.search(r"\d{3,}", s)))
        f_url   = int(bool(re.search(r"https?://|www\.", s.lower())))
        feats.append([f_api,f_policy,f_error,f_price,f_prof,f_digit,f_url])
    return np.array(feats, dtype=float)
