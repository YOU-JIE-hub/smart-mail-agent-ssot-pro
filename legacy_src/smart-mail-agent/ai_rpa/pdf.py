__all__=["extract_text"]
def extract_text(path:str, **kw): 
    try:
        import pathlib
        return f"[offline-pdf] {pathlib.Path(path).name}"
    except Exception:
        return ""
