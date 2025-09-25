import os, sys, types, importlib, datetime
from pathlib import Path

def test_cov_pad_more(tmp_path):
    # ---------- OCR: utf-8 / 非 utf-8 / 路徑 ----------
    import ai_rpa.ocr as ocr
    assert "text" in ocr.ocr_bytes(b"hello")                     # utf-8
    assert "text" in ocr.ocr_bytes(b"\xff\xfe\x00\x01")          # 非 utf-8 分支
    p = tmp_path/"x.bin"; p.write_bytes(b"\x00\x01abc")
    assert "text" in ocr.ocr_path(str(p))                        # path 分支

    # ---------- json_safe：各種邊界 + 別名 API ----------
    from ai_rpa.utils import json_safe as js
    class C: pass
    src = {3: C(), "b": b"\xff", "s": {1,2}, "dt": datetime.datetime(2024,1,1), "e": ValueError("x")}
    safe = js.ensure_jsonable(src)
    s1 = js.dumps_safe(safe); assert isinstance(s1, str) and s1.startswith("{")
    outp = tmp_path/"j.json"; js.dump_safe(safe, outp); assert outp.exists()
    # 別名
    assert isinstance(js.json_dumps(safe), str)
    assert isinstance(js.dumps(safe), str)
    js.dump(safe, tmp_path/"j2.json")

    # ---------- spam_adapter：規則法 / ML 分支 ----------
    import ai_rpa.spam_adapter as sa
    os.environ.pop("SMA_SPAM_BACKEND", None)
    importlib.reload(sa)
    r_rule = sa.score("this is FREE money!!!")
    assert isinstance(r_rule, dict) and r_rule["score"] >= 1.0 and any("kw_match" in x for x in r_rule.get("reasons",[]))

    # 構造假的 ML 服務供 ML 分支使用
    os.environ["SMA_SPAM_BACKEND"] = "ml"
    sml = types.ModuleType("models.spam.serving_ml")
    def available(): return True
    def score_prob_spam(text): return 0.42
    sml.available = available; sml.score_prob_spam = score_prob_spam
    sys.modules["models.spam"] = types.ModuleType("models.spam")
    sys.modules["models.spam.serving_ml"] = sml
    importlib.reload(sa)
    r_ml = sa.score(["hello","world"])
    assert 0.41 < r_ml["score"] < 0.43 and "ml_prob" in r_ml.get("reasons",[])

    # ---------- file_classifier：多種副檔名 / 內容 ----------
    import ai_rpa.file_classifier as fc
    j = tmp_path/"data.json"; j.write_text('{"a":1}', encoding="utf-8")
    fr_j = fc.classify_file(j); assert "data" in fr_j["labels"]

    b = tmp_path/"bin.bin"; b.write_bytes(b"\x00"*32)
    fr_b = fc.classify_file(b); assert "binary" in fr_b["labels"]

    txt = tmp_path/"quote.txt"; txt.write_text("請提供報價與價格明細", encoding="utf-8")
    fr_t = fc.classify_text(txt.read_text("utf-8"))
    assert any(x in fr_t["labels"] for x in ("quote","document","text"))

    fr_bytes = fc.classify_bytes(b'{"k":2}')
    assert isinstance(fr_bytes, dict)

    dr = fc.classify_dir(tmp_path)
    assert isinstance(dr, list) and len(dr) >= 3

    # ---------- nlp：規則分支 / ML 分支 ----------
    import ai_rpa.nlp as nlp
    os.environ.pop("SMA_INTENT_BACKEND", None)
    importlib.reload(nlp)
    r1 = nlp.classify("想了解退款機制與使用限制")
    a1 = nlp.analyze_text("free money for quote")
    assert "policy_qa" in r1["intents"] and "summary" in a1

    os.environ["SMA_INTENT_BACKEND"] = "ml"
    iml = types.ModuleType("models.intent.serving_ml")
    def available_i(): return True
    def predict(text): return {"intents":["sales"], "labels":["biz_quote"], "length": len(text.split())}
    iml.available = available_i; iml.predict = predict
    sys.modules["models.intent"] = types.ModuleType("models.intent")
    sys.modules["models.intent.serving_ml"] = iml
    importlib.reload(nlp)
    r2 = nlp.classify("合作 報價")
    assert "sales" in r2["intents"]
