# --- [HOTFIX] bind rules_feat & vendor path BEFORE joblib.load ---
import os, sys, importlib.util
VENDOR=os.path.normpath(os.path.join(os.path.dirname(__file__),"..","vendor"))
if os.path.isdir(VENDOR) and VENDOR not in sys.path:
    sys.path.insert(0, VENDOR)
RULES_SRC=os.environ.get("SMA_RULES_SRC")
if RULES_SRC and os.path.isfile(RULES_SRC):
    spec=importlib.util.spec_from_file_location("train_rules_impl", RULES_SRC)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    # 為不同歷史別名註冊同一份模組
    for alias in (
        "train_pro_fresh","train_pro",
        "intent_bundle_intent__sma_tools_runtime_threshold_router_py",
        "sma_tools.runtime_threshold_router","runtime_threshold_router",
        "vendor.rules_features"
    ):
        sys.modules[alias]=mod
    # 也把 rules_feat 掛在 __main__（歷史 pickle 會找 __main__.rules_feat）
    try:
        import __main__ as __M__; __M__.rules_feat=getattr(mod,"rules_feat",None)
    except Exception:
        pass
# --- [END HOTFIX] ---
