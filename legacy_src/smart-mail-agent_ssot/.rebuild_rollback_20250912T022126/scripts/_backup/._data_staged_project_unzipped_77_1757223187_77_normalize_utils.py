import re
from datetime import datetime, timedelta
from dateutil import parser as dateparser, tz

_CCY_MAP = {"TWD": "TWD", "NTD": "TWD", "NT$": "TWD", "USD": "USD", "US$": "USD"}

def norm_currency(token:str):
    token = token.strip().upper(); return _CCY_MAP.get(token, token)

def norm_amount(text:str):
    t = text.strip(); scope=None; t_clean=t.replace(",", "")
    m = re.search(r'^(?P<ccy>NT\$|NTD|TWD|USD|US\$)\s?(?P<num>[0-9]+(?:\.[0-9]{1,2})?)$', t, re.I)
    if m:
        return m.group("num"), norm_currency(m.group("ccy")), text, scope
    m = re.search(r'^(?P<num>[0-9]+(?:\.[0-9]+)?)\s?(?P<suf>k|m)\s?(?P<ccy>twd|ntd|nt\$|usd|us\$)?$', t, re.I)
    if m:
        num = float(m.group("num")); mul = 1000 if m.group("suf").lower()=="k" else 1_000_000
        return f"{num*mul:.0f}", norm_currency(m.group("ccy") or ""), text, scope
    if re.fullmatch(r'[0-9]+(\.[0-9]{1,2})?', t_clean):
        return t_clean, "", text, scope
    return None

def norm_percent(text:str):
    m = re.search(r'([0-9]{2}(?:\.[0-9]{1,2})?)\s?%', text); return f"{m.group(1)}%" if m else None

def _floor_to_1700(dt):
    return dt.replace(hour=17, minute=0, second=0, microsecond=0)

def _week_end(dt):
    delta = (4 - dt.weekday()) % 7; return _floor_to_1700(dt + timedelta(days=delta))

def _month_end(dt):
    nxt = (dt.replace(day=28) + timedelta(days=4)).replace(day=1); return _floor_to_1700(nxt - timedelta(days=1))

def norm_datetime(raw:str, ref_tz:str="+08:00"):
    tzinfo = tz.gettz(f"Etc/GMT{-int(ref_tz.split(':')[0]):+d}") if ref_tz else None
    now = datetime.now(tzinfo); lo = raw.lower()
    if any(k in lo for k in ("eod","下班前","今日結束")): return _floor_to_1700(now).isoformat()
    if any(k in lo for k in ("eow","本週結束","週末前")): return _week_end(now).isoformat()
    if any(k in lo for k in ("eom","月底前","本月結束")): return _month_end(now).isoformat()
    ampm = "PM" if ("下午" in lo or "pm" in lo) else ("AM" if ("上午" in lo or "am" in lo) else "")
    try:
        dt = dateparser.parse(raw + (" "+ampm if ampm else ""))
        if dt:
            if tzinfo: dt = dt.replace(tzinfo=tzinfo) if dt.tzinfo is None else dt.astimezone(tzinfo)
            return dt.isoformat()
    except Exception:
        pass
    return None

def norm_duration(text:str):
    m = re.search(r'([0-9]+)\s*(m|min|分鐘|h|hr|小時)', text, re.I)
    if not m: return None
    n=int(m.group(1)); unit=m.group(2).lower()
    return f"{n}h" if unit in ("h","hr","小時") else f"{n}m"

def norm_env(text:str):
    lo=text.lower()
    if any(k in lo for k in ("prod","生產","prd","production")): return "prod"
    if "uat" in lo: return "UAT"
    if any(k in lo for k in ("sandbox","測試")): return "sandbox"
    return None
