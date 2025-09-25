from pathlib import Path
import json
from .conftest import run_script

def test_kie_eval_strict(tmp_path):
    # 建 2 筆，有 2 個命中
    test = tmp_path/"kie.jsonl"
    rows = [
        {"id":"a","text":"amount 123 and 2025-09-30", "spans":[{"label":"amount","start":7,"end":10},{"label":"date_time","start":15,"end":25}]},
        {"id":"b","text":"no spans", "spans":[]},
    ]
    test.write_text("\n".join(json.dumps(r,ensure_ascii=False) for r in rows), encoding="utf-8")
    outp = tmp_path/"rep"
    run_script(Path(".sma_tools/kie_eval_strict.py"), [
        "--model_dir", "reports_auto/kie/kie",  # 會被 fake transformers 接管
        "--test", str(test),
        "--out_prefix", str(outp)
    ])
    txt = Path(f"{outp}.txt")
    tsv = Path(f"{outp}_per_label.tsv")
    assert txt.exists() and tsv.exists()
    t = txt.read_text(encoding="utf-8")
    assert "strict_span_P" in t and "strict_span_F1" in t
