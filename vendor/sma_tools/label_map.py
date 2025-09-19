ZH2EN = {
  "報價":"biz_quote", "技術支援":"tech_support", "資料異動":"profile_update",
  "規則詢問":"policy_qa", "投訴":"complaint", "其他":"other"
}
EN2ZH = {v:k for k,v in ZH2EN.items()}
EN_LABELS = ["biz_quote","complaint","other","policy_qa","profile_update","tech_support"]
def normalize_labels(labels, target="en"):
    if target=="en": conv = ZH2EN; passthru = set(EN2ZH.keys())
    else:            conv = EN2ZH; passthru = set(ZH2EN.keys())
    out=[]
    for x in labels:
        s = ("" if x is None else str(x))
        if s in conv: out.append(conv[s])
        elif s in passthru: out.append(s)
        else: out.append("other")
    return out
