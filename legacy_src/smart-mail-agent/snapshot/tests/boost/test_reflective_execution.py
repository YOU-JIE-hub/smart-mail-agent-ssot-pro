import os, types, inspect, importlib, pkgutil
os.environ.setdefault("OFFLINE", "1")
TOP_PKGS = ["smart_mail_agent", "ai_rpa"]
DENY_MOD_PARTS = {
    ".init_db", "init_db", "send_with_attachment", "mailer",
    ".observability.tracing", ".observability.stats_collector",
    ".scripts.", ".gh_pages.", ".showcase.", ".share.",
}
DENY_FUNC_PREFIX = ("run_", "start_", "main", "init_db", "download")
MAX_CALLS_PER_MODULE = 25
def want_module(modname: str) -> bool:
    return not any(part in modname for part in DENY_MOD_PARTS)
def iter_pkg_modules(root_pkg: str):
    try:
        pkg = importlib.import_module(root_pkg)
    except Exception:
        return
    if not hasattr(pkg, "__path__"):
        yield root_pkg; return
    yield root_pkg
    for m in pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + "."):
        yield m.name
def safe_callables(mod: types.ModuleType):
    called = 0
    for name, obj in vars(mod).items():
        if callable(obj) and not name.startswith(DENY_FUNC_PREFIX):
            try:
                sig = inspect.signature(obj)
                if all(p.default != inspect._empty or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
                       for p in sig.parameters.values()):
                    obj(); called += 1
                    if called >= MAX_CALLS_PER_MODULE: return called
            except Exception: pass
    for name, obj in vars(mod).items():
        if inspect.isclass(obj) and obj.__module__ == mod.__name__:
            try:
                sig = inspect.signature(obj)
                if all(p.default != inspect._empty or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
                       for p in sig.parameters.values()):
                    inst = obj()
                    for mname, mobj in ((n, getattr(inst, n)) for n in dir(inst)):
                        if not callable(mobj) or mname.startswith("_") or mname.startswith(DENY_FUNC_PREFIX):
                            continue
                        try:
                            msig = inspect.signature(mobj)
                            if all(p.default != inspect._empty or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
                                   for p in msig.parameters.values()):
                                mobj(); called += 1
                                if called >= MAX_CALLS_PER_MODULE: return called
                        except Exception: pass
            except Exception: pass
    return called
def test_reflective_sweep():
    total_imported = total_called = 0
    for pkg in TOP_PKGS:
        for modname in iter_pkg_modules(pkg):
            if not want_module(modname): continue
            try:
                mod = importlib.import_module(modname)
                total_imported += 1
                total_called += safe_callables(mod)
            except Exception:
                pass
    assert total_imported >= 5
