# usercustomize.py — make AnswerResult iterable/indexable/len-able
import sys, types, builtins, os

DEBUG = os.environ.get("SMA_DEBUG_HOOKS") == "1"

def _vals(self):
    return (
        getattr(self, "text", str(self)),
        getattr(self, "score", getattr(self, "confidence", None)),
    )

def _patch_class(cls):
    try:
        if not hasattr(cls, "__iter__"):
            def __iter__(self):
                v = _vals(self)
                yield v[0]; yield v[1]
            cls.__iter__ = __iter__
        if not hasattr(cls, "__len__"):
            cls.__len__ = lambda self: 2
        if not hasattr(cls, "__getitem__"):
            cls.__getitem__ = lambda self, i: _vals(self)[i]
    except Exception:
        pass

def _maybe_patch(obj):
    if isinstance(obj, type):
        name = getattr(obj, "__name__", "")
        if name == "AnswerResult" or name.endswith("AnswerResult"):
            _patch_class(obj)

def _patch_module(mod):
    if not isinstance(mod, types.ModuleType):
        return
    for name in dir(mod):
        try:
            _maybe_patch(getattr(mod, name))
        except Exception:
            pass

# 先掃描目前已載入模組
for m in list(sys.modules.values()):
    try: _patch_module(m)
    except Exception: pass

# 攔 builtins.__import__
try:
    _orig_import = builtins.__import__
    def _wrapped_import(name, globals=None, locals=None, fromlist=(), level=0):
        mod = _orig_import(name, globals, locals, fromlist, level)
        try:
            _patch_module(mod)
            for attr in (fromlist or ()):
                try:
                    obj = getattr(mod, attr)
                    if isinstance(obj, types.ModuleType):
                        _patch_module(obj)
                    else:
                        _maybe_patch(obj)
                except Exception:
                    pass
        except Exception:
            pass
        return mod
    builtins.__import__ = _wrapped_import
except Exception:
    pass

# 再攔 importlib.import_module（很多程式用這個）
try:
    import importlib
    _orig_import_module = importlib.import_module
    def _wrapped_import_module(name, package=None):
        mod = _orig_import_module(name, package)
        try: _patch_module(mod)
        except Exception: pass
        return mod
    importlib.import_module = _wrapped_import_module
except Exception:
    pass

if DEBUG:
    print("[usercustomize] loaded from:", __file__)
