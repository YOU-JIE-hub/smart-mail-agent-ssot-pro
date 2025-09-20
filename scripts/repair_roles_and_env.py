import os, sys, json, shutil
from pathlib import Path

def load_any(p):
    import joblib, builtins
    # 反序列化 shim
    sys.modules.setdefault("__main__", builtins)
    setattr(sys.modules["__main__"], "rules_feat", lambda x: {})
    setattr(sys.modules["__main__"], "rules_feat_func", lambda x: {})
    obj = joblib.load(p)
    if isinstance(obj, dict):
        for k in ("pipeline","model","clf"):
            if k in obj: return obj[k]
    return obj

def sig(path):
    try:
        pipe = load_any(path)
        steps = [n for n,_ in getattr(pipe, "steps", [])] or [pipe.__class__.__name__.lower()]
        last = pipe.steps[-1][1] if hasattr(pipe,"steps") else pipe
        classes = getattr(last, "classes_", None) or getattr(pipe, "classes_", None)
        vocab = None
        if hasattr(pipe, "steps"):
            for n,s in pipe.steps:
                if hasattr(s,"vocabulary_"):
                    v = getattr(s,"vocabulary_", None)
                    vocab = len(v) if v is not None else None
        else:
            if hasattr(pipe,"vocabulary_"): vocab = len(pipe.vocabulary_)
        cls = list(map(str,classes)) if classes is not None else None
        return {"ok": True, "path": str(path), "steps": steps,
                "classes": cls, "n_classes": len(cls) if cls else None,
                "vocab_size": vocab}
    except Exception as e:
        return {"ok": False, "path": str(path), "error": repr(e)}

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / f"reports_auto/roles_fix"
out.mkdir(parents=True, exist_ok=True)

# 候選：已裝在 repo 的兩顆 + 你指定的 spam 鎖定
cands = []
repo_intent = ROOT/"models/intent/artifacts/model_pipeline.pkl"
repo_spam   = ROOT/"models/spam/artifacts/model_pipeline.pkl"
lock_spam   = os.environ.get("SPAM_PKL")
for p in [repo_intent, repo_spam, lock_spam]:
    if p and Path(p).exists(): cands.append(str(Path(p).resolve()))
cands = sorted(set(cands))
sigs = [sig(p) for p in cands]

# 選角：多類 → intent；二類 → spam；顯性 lock_spam 優先
multi  = [s for s in sigs if s.get("ok") and (s.get("n_classes") or 0) >= 3]
binary = [s for s in sigs if s.get("ok") and s.get("n_classes")==2]

spam_pick = None
if lock_spam:
    for s in binary:
        if Path(s["path"]).resolve()==Path(lock_spam).resolve(): spam_pick = s; break
if not spam_pick and binary: spam_pick = binary[0]

intent_pick = multi[0] if multi else None
# 若沒有多類，且 repo 兩顆其中一顆不是 lock_spam，就用另一顆暫填
if not intent_pick:
    for s in sigs:
        if spam_pick and Path(s["path"]).resolve()==Path(spam_pick["path"]).resolve(): continue
        if s.get("ok"): intent_pick = s; break

# 寫入標準槽位
final_intent = repo_intent; final_spam = repo_spam
final_intent.parent.mkdir(parents=True, exist_ok=True)
final_spam.parent.mkdir(parents=True, exist_ok=True)

ops=[]
def cp(src, dst):
    shutil.copy2(src, dst); ops.append({"from":src, "to":str(dst)})

if intent_pick: cp(intent_pick["path"], final_intent)
if spam_pick:   cp(spam_pick["path"],   final_spam)

# 煙霧測試
def smoke(p):
    try:
        m = load_any(str(p))
        return list(map(str, m.predict(["FREE $$$ click here!!!","請問資料怎麼改？","我要投訴"])))
    except Exception as e:
        return f"predict_failed: {e}"

summary = {
  "candidates": sigs,
  "picked": {"intent": intent_pick, "spam": spam_pick},
  "final_paths": {"intent_pkl": str(final_intent), "spam_pkl": str(final_spam)},
  "smoke": {"intent": smoke(final_intent), "spam": smoke(final_spam)},
  "ops": ops,
}
(out/"SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")
(out/"MODEL_PATHS.auto.env").write_text(
    f'INTENT_PKL="{final_intent}"\nSPAM_PKL="{final_spam}"\n', "utf-8"
)
print(json.dumps(summary, ensure_ascii=False, indent=2))
print(f'\n=== MODEL ENV ===\nINTENT_PKL="{final_intent}"\nSPAM_PKL="{final_spam}"\n')
print(f"匯入：  set -a; . {out/'MODEL_PATHS.auto.env'}; set +a")
