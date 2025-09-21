from __future__ import annotations
import json, sys
from pathlib import Path

def test_rules_default_sales_and_support(tmp_path):
    from ai_rpa.nlp import analyze_text
    t = "想要合作，也遇到發票問題需要退款"
    out = analyze_text([t], model="rules:default")
    # 兩個意圖都能命中（資料驅動、不綁死單一關鍵字）
    assert "sales" in out["intents"] and "support" in out["intents"]

def test_rules_custom_yaml_override(tmp_path):
    # 客製規則：新增一個自定關鍵字「聯繫採購」→ 歸類到 sales
    yml = tmp_path / "custom.yml"
    yml.write_text(
        """
version: 1
intents:
  sales:
    any: ["聯繫採購"]
    all: []
    none: []
    weight: 1.0
""".strip(),
        encoding="utf-8",
    )
    from ai_rpa.nlp import analyze_text
    out = analyze_text("請盡快聯繫採購，謝謝", model=f"rules:{yml}")
    assert "sales" in out["intents"]

def test_rules_all_and_none(tmp_path):
    # 測試 all/none 條件
    yml = tmp_path / "custom2.yml"
    yml.write_text(
        """
version: 1
intents:
  vip_refund:
    any: ["退款"]
    all: ["VIP"]
    none: ["測試"]
    weight: 1.0
""".strip(),
        encoding="utf-8",
    )
    from ai_rpa.nlp import analyze_text
    # 1) 有任何詞 + all 條件成立
    o1 = analyze_text("VIP 客戶要求退款", model=f"rules:{yml}")
    assert "vip_refund" in o1["intents"]
    # 2) 命中 none → 不該觸發
    o2 = analyze_text("VIP 客戶測試退款流程", model=f"rules:{yml}")
    assert "vip_refund" not in o2["intents"]
