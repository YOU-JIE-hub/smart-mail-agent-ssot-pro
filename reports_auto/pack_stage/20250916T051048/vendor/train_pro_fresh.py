import os, importlib.util, sys
SRC=os.environ.get("SMA_RULES_SRC")
if not SRC or not os.path.isfile(SRC): raise FileNotFoundError(f"SMA_RULES_SRC invalid: {SRC!r}")
spec=importlib.util.spec_from_file_location("runtime_threshold_router_impl", SRC)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
for nm in ["train_pro_fresh","train_pro","sma_tools.runtime_threshold_router","runtime_threshold_router","vendor.rules_features"]:
    sys.modules[nm]=m
import __main__ as MAIN
if hasattr(m,"rules_feat"): MAIN.rules_feat=m.rules_feat
