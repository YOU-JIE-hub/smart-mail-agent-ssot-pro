import sys, types
def install():
    try:
        import vendor.rules_features as rf  # 你專案裡的特徵函式
    except Exception:
        rf = None
    fn = None
    for name in ("rules_feat_func","rules_feat"):
        if rf is not None and hasattr(rf, name):
            fn = getattr(rf, name); break
    if fn is None:
        def fn(text): return {"len": len(text or "")}  # 退化版，至少能解 pickle
    m = sys.modules.get("__main__")
    if not isinstance(m, types.ModuleType):
        m = types.ModuleType("__main__"); sys.modules["__main__"] = m
    m.rules_feat = fn
    m.rules_feat_func = fn
