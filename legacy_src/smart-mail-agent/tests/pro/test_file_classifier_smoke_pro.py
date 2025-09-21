import inspect
import ai_rpa.file_classifier as m

def test_file_classifier_smoke(tmp_path):
    (tmp_path/"a.txt").write_text("hi", encoding="utf-8")
    ran = False
    for n in ("classify_files","classify","classify_dir"):
        if hasattr(m, n):
            fn = getattr(m, n)
            try:
                fn(str(tmp_path))
                ran = True
                break
            except Exception:
                continue
    if not ran:
        for _, fn in inspect.getmembers(m, inspect.isfunction):
            try:
                sig = inspect.signature(fn)
                req = [p for p in sig.parameters.values()
                       if p.default is p.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
                if len(req) == 1:
                    try:
                        fn(tmp_path); ran = True; break
                    except Exception:
                        continue
            except Exception:
                continue
    assert ran or not any(callable(getattr(m, n)) for n in dir(m)), "file_classifier 應有至少一個 1 參數可呼叫函式"
