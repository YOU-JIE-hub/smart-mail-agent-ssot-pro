import sys, importlib.util, types, pathlib
root = pathlib.Path(__file__).resolve().parent
tp = root / "train_pro_fresh.py"
spec = importlib.util.spec_from_file_location("train_pro_fresh", tp)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
# 讓 pickle 在不同進程/腳本下也能拿到同名符號
sys.modules["train_pro_fresh"] = m
# 一些舊 pickle 會指向 __main__，一併映射
main = sys.modules.get("__main__")
if isinstance(main, types.ModuleType):
    for name in ("rules_feat","ZeroPad","DictFeaturizer"):
        setattr(main, name, getattr(m, name))
print("[import-fix] train_pro_fresh loaded; rules_feat dims test ->",
      m.rules_feat(["報價單詢問","系統錯誤無法登入"]).shape)
