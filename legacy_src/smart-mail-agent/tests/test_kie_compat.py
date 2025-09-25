import json, os
def _pick_kie_dir():
    for p in ("kie","reports_auto/kie/kie"):
        if os.path.isdir(p): return p
    raise AssertionError("KIE model dir missing (kie/ or reports_auto/kie/kie/)")
def test_kie_id2label_compatible():
    kd = _pick_kie_dir()
    cfg = json.load(open(os.path.join(kd,"config.json"),"r",encoding="utf-8"))
    assert cfg.get("id2label") or cfg.get("label2id"), "both id2label and label2id missing"
