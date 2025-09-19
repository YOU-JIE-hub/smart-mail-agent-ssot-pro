import os, sys, glob, importlib.util
CANDS=[
  "intent/**/.sma_tools/runtime_threshold_router.py",
  "intent/**/runtime_threshold_router.py",
  "src/**/runtime_threshold_router.py",
  "src/**/rules_features.py",
  "**/runtime_threshold_router.py",
  "**/rules_features.py",
]
EXCL=(os.sep+".venv"+os.sep, os.sep+"reports_auto"+os.sep, os.sep+"dist"+os.sep, os.sep+"build"+os.sep)
def _load(fp:str):
    spec=importlib.util.spec_from_file_location("_rt_router_dyn_", fp)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)  # type: ignore
    sys.modules.setdefault("runtime_threshold_router", mod)
    sys.modules.setdefault("sma_tools.runtime_threshold_router", mod)
    g=globals()
    for k in dir(mod):
        if not k.startswith("_"): g[k]=getattr(mod,k)
for pat in CANDS:
    for p in sorted(glob.glob(pat, recursive=True)):
        ap=os.path.abspath(p)
        if any(e in ap for e in EXCL): continue
        try:
            _load(ap)
            if "rules_feat" in globals():
                sys.modules.setdefault("train_pro", sys.modules[__name__])
                _BRIDGE_SOURCE=ap
                raise SystemExit
        except SystemExit:
            raise
        except Exception:
            pass
raise ImportError("rules_feat not found for bridge; 請把含 rules_feat 的 runtime_threshold_router.py 放回專案（intent/.sma_tools/ 或 src/ 下）")
