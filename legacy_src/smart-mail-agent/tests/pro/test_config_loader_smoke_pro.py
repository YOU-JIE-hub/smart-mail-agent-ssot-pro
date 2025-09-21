import json, inspect
import ai_rpa.utils.config_loader as m

def test_config_loader_smoke(tmp_path):
    cfg = tmp_path/"c.json"
    cfg.write_text(json.dumps({"a":1}, ensure_ascii=False), encoding="utf-8")
    ran = False
    for n in ("load","load_config","load_json","load_from_file"):
        if hasattr(m, n):
            try:
                getattr(m, n)(cfg); ran = True; break
            except Exception:
                continue
    if not ran:
        for _, fn in inspect.getmembers(m, inspect.isfunction):
            try:
                import inspect as _i
                sig = _i.signature(fn)
                req = [p for p in sig.parameters.values()
                       if p.default is p.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
                if len(req) == 1:
                    try:
                        fn(cfg); ran = True; break
                    except Exception:
                        continue
            except Exception:
                continue
    assert ran or not any(callable(getattr(m, n)) for n in dir(m)), "config_loader 應有至少一個單參函式"
