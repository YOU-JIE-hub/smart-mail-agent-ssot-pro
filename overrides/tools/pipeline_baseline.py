import os,sys,importlib.util,re; from pathlib import Path
_ORIG=Path(__file__).resolve().parents[2]/"tools"/"pipeline_baseline.py"
spec=importlib.util.spec_from_file_location("orig", str(_ORIG)); orig=importlib.util.module_from_spec(spec); spec.loader.exec_module(orig)
globals().update({k:getattr(orig,k) for k in dir(orig) if not k.startswith("_")})
def _pred():
  p=os.environ.get("SMA_RULES_SRC","");
  if not p: return None
  try:
    s=importlib.util.spec_from_file_location("rr", p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
    if hasattr(m,"predict_one"): return m.predict_one
    if hasattr(m,"predict"): return lambda t:(m.predict([t]) or ["other"])[0]
  except Exception: return None
def classify_rule(email=None, contract=None, **kw):
  tx = email.get("text","") if isinstance(email,dict) else (email or "")
  f=_pred()
  if f:
    try: return f(tx) or "other"
    except Exception: pass
  return orig.classify_rule(email=email, contract=contract, **kw)
def extract_slots_rule(email=None, intent=None, **kw):
  t = email.get("text","") if isinstance(email,dict) else (email or "")
  s={"price":None,"qty":None,"id":None}
  m=re.search(r"(?:\\$|NTD?\\s*|新台幣\\s*)?([0-9][\\d,\\.]{2,})\\s*(?:元|NTD?|塊|萬)?",t,re.I);
  if m:
    num=m.group(1).replace(",",""); s["price"]=(float(num) if "." in num else (int(num) if num.isdigit() else num))
  q=re.search(r"(?:數量|共|各|x|×)?\\s*([0-9]+)\\s*(?:台|部|件|個)?",t,re.I); s["qty"]=int(q.group(1)) if q else None
  i=re.search(r"\\b([A-Z]{2,}-?\\d{4,})\\b",t); s["id"]=i.group(1) if i else None
  return s
