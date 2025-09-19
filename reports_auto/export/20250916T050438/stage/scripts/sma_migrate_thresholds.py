#!/usr/bin/env python3
import json, shutil, time
from pathlib import Path

ROOT = Path("/home/youjie/projects/smart-mail-agent_ssot")
TS = time.strftime("%Y%m%dT%H%M%S")

INTENT_ZH = ["報價","技術支援","投訴","規則詢問","資料異動","其他"]
INTENT_EN2ZH = {
    "biz_quote":"報價","tech_support":"技術支援","complaint":"投訴",
    "policy_qa":"規則詢問","profile_update":"資料異動","other":"其他"
}

def load_json(p):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def backup(p):
    if p.exists():
        bak = p.with_suffix(p.suffix+f".bak_{TS}")
        shutil.copy2(p, bak)
        return str(bak)
    return None

def normalize_spam():
    p = ROOT/"artifacts_prod"/"ens_thresholds.json"
    j = load_json(p)
    if j is None:
        print("[WARN] 無 spam 門檻檔，略過"); return
    thr = None
    # 支援的舊格式
    # 1) {"spam":0.5}
    # 2) {"threshold":0.5} 或 {"pos":0.5}
    # 3) {"p1":0.52,"margin":-0.02} -> p1+margin
    # 4) {"spam":{"threshold":0.5}} 或 {"spam_threshold":0.5}
    candidates = []
    if isinstance(j, dict):
        if isinstance(j.get("spam"), (int,float)): thr = float(j["spam"])
        elif isinstance(j.get("spam"), dict):
            for k in ["thr","threshold","pos","p1"]: 
                if k in j["spam"]: thr=float(j["spam"][k]); break
        for k in ["threshold","pos","spam_threshold"]:
            if thr is None and k in j and isinstance(j[k], (int,float)): thr = float(j[k])
        if thr is None and "p1" in j:
            m = float(j.get("margin", 0.0))
            thr = max(0.0, min(1.0, float(j["p1"]) + m))
    if thr is None:
        raise SystemExit("[FATAL] 無法從 ens_thresholds.json 解析出 spam 門檻")
    backup(p)
    p.write_text(json.dumps({"spam": float(thr)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] spam 門檻已標準化 -> {p}  (spam={thr})")

def normalize_intent():
    p = ROOT/"reports_auto"/"intent_thresholds.json"
    j = load_json(p)
    if j is None:
        # 建一份預設
        j = {"default":0.50}
    # 可能的舊格式：
    # A) 每類英文鍵：{"biz_quote":0.55,...}
    # B) 統一策略：{"threshold":0.5} 或 {"default":0.5} 或 {"p1":0.52,"margin":0.0}
    # C) 每類中文鍵（正確）：{"報價":0.55,...}
    out = {}
    if any(k in j for k in ["threshold","default","p1"]):
        if "p1" in j:
            thr = float(j["p1"]) + float(j.get("margin", 0.0))
        else:
            thr = float(j.get("threshold", j.get("default", 0.5)))
        for k in INTENT_ZH:
            out[k] = 0.40 if k=="其他" else float(thr)
    elif any(k in j for k in INTENT_EN2ZH.keys()):
        for en, zh in INTENT_EN2ZH.items():
            if en in j: out[zh] = float(j[en])
        # 沒提供的補上預設
        for k in INTENT_ZH:
            out.setdefault(k, 0.40 if k=="其他" else 0.50)
    else:
        # 假如已是中文但缺鍵，補足
        for k in INTENT_ZH:
            if k in j and isinstance(j[k], (int,float)): out[k] = float(j[k])
        if not out:
            raise SystemExit("[FATAL] 無法從 intent_thresholds.json 解析各類門檻")
        for k in INTENT_ZH:
            out.setdefault(k, 0.40 if k=="其他" else 0.50)
    backup(p)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] intent 門檻已標準化 -> {p}")
    for k in INTENT_ZH:
        print("  -", k, "=", out[k])

if __name__ == "__main__":
    normalize_spam()
    normalize_intent()
    print("[DONE] thresholds migrated")
