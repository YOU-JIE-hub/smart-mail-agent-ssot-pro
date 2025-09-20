import os, json, sys, shutil
from pathlib import Path

def load_any(p):
    import joblib, builtins
    sys.modules.setdefault("__main__", builtins)
    # 反序列化 shim（舊 pickled 期望）
    setattr(sys.modules["__main__"], "rules_feat", lambda x: {})
    setattr(sys.modules["__main__"], "rules_feat_func", lambda x: {})
    obj = joblib.load(p)
    if isinstance(obj, dict):
        for k in ("pipeline","model","clf"):
            if k in obj: return obj[k]
    return obj

def signature(p):
    try:
        pipe = load_any(p)
        steps = [n for n,_ in getattr(pipe, "steps", [])] or [pipe.__class__.__name__.lower()]
        classes = None
        vocab = None
        if hasattr(pipe, "steps"):
            last = pipe.steps[-1][1]
            classes = getattr(last, "classes_", None) or getattr(pipe, "classes_", None)
            for n,s in pipe.steps:
                if hasattr(s, "vocabulary_"):
                    vocab = len(getattr(s,"vocabulary_", {}) or {})
        else:
            classes = getattr(pipe, "classes_", None)
            if hasattr(pipe, "vocabulary_"): vocab = len(pipe.vocabulary_)
        c = list(classes) if classes is not None else None
        return {"ok": True, "path": p, "steps": steps, "classes": c,
                "n_classes": len(c) if c else None, "vocab_size": vocab}
    except Exception as e:
        return {"ok": False, "path": p, "error": repr(e)}

ROOT = Path(__file__).resolve().parents[1]
outdir = ROOT / f"reports_auto/roles_{os.environ.get('TS','') or ''}"
outdir.mkdir(parents=True, exist_ok=True)

# 候選路徑
candidates = []
env_spam = os.environ.get("SPAM_PKL")
env_intent = os.environ.get("INTENT_PKL")
if env_spam: candidates.append(("hint_spam", env_spam))
if env_intent: candidates.append(("hint_intent", env_intent))
candidates += [
    ("repo_spam", str(ROOT/"models/spam/artifacts/model_pipeline.pkl")),
    ("repo_intent", str(ROOT/"models/intent/artifacts/model_pipeline.pkl")),
    ("inbox_spam", "/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"),
]

seen = {}
sigs = []
for tag, p in candidates:
    if not p or not Path(p).exists(): continue
    rp = str(Path(p).resolve())
    if rp in seen: continue
    seen[rp] = tag
    sig = signature(rp)
    sig["tag"] = tag
    sigs.append(sig)

# 選擇角色
multi = [s for s in sigs if s.get("ok") and (s.get("n_classes") or 0) >= 3]
binary = [s for s in sigs if s.get("ok") and (s.get("n_classes") == 2)]

# spam 以 env_spam 優先，否則用任何二分類
spam_pick = None
if env_spam and any(Path(s["path"]).resolve()==Path(env_spam).resolve() for s in binary):
    spam_pick = [s for s in binary if Path(s["path"]).resolve()==Path(env_spam).resolve()][0]
elif binary:
    spam_pick = binary[0]

# intent 用多分類；若沒有多分類，就退而求其次：取非 env_spam 的另一顆（避免空）
intent_pick = multi[0] if multi else None
if not intent_pick:
    for s in sigs:
        if spam_pick and Path(s["path"]).resolve()==Path(spam_pick["path"]).resolve(): continue
        if s.get("ok"): intent_pick = s; break

# 複製到標準槽位
final_intent = ROOT/"models/intent/artifacts/model_pipeline.pkl"
final_spam   = ROOT/"models/spam/artifacts/model_pipeline.pkl"
final_intent.parent.mkdir(parents=True, exist_ok=True)
final_spam.parent.mkdir(parents=True, exist_ok=True)

ops = {"copied": []}
def cp(src, dst):
    shutil.copy2(src, dst); ops["copied"].append({"from": str(src), "to": str(dst)})

if intent_pick: cp(intent_pick["path"], final_intent)
if spam_pick:   cp(spam_pick["path"],   final_spam)

# ENV 檔
env_fp = outdir/"MODEL_PATHS.auto.env"
env_fp.write_text(
    f'INTENT_PKL="{final_intent}"\nSPAM_PKL="{final_spam}"\n',
    encoding="utf-8"
)

# 煙霧測試 & 類別對齊提示
def smoke(p):
    try:
        m = load_any(str(p))
        pred = m.predict(["FREE $$$ click here!!!","請問資料怎麼改？","我要投訴"])
        return list(map(str,pred))
    except Exception as e:
        return f"predict_failed: {e}"

summary = {
    "picked": {
        "intent": intent_pick,
        "spam":   spam_pick,
    },
    "final_paths": {
        "intent_pkl": str(final_intent),
        "spam_pkl":   str(final_spam),
    },
    "smoke": {
        "intent": smoke(final_intent),
        "spam":   smoke(final_spam),
    },
    "notes": []
}

# 0/1 → ham/spam 映射猜測（僅提示，不強行改模型）
sp = spam_pick["classes"] if (spam_pick and spam_pick.get("classes")) else None
if sp and set(sp)=={"0","1"}:
    s = summary["smoke"]["spam"]
    if isinstance(s, list):
        summary["notes"].append("guess: '1' ≈ spam（因 'FREE $$$' 預測為 1）" if s[0]=="1" else "guess: '0' ≈ spam（煙霧測試顯示 FREE $$$→0）")

# 落檔
(outdir/"SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
print(f"\n=== MODEL ENV ===\nINTENT_PKL=\"{final_intent}\"\nSPAM_PKL=\"{final_spam}\"\n")
print(f"匯入：  set -a; . {env_fp}; set +a")
