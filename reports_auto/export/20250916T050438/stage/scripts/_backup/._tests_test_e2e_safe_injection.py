#!/usr/bin/env python3
# 檔案位置: tests/test_e2e_safe_injection.py
# 模組用途: 驗證 e2e_safe 的輔助方法能建立 sample_eml 與 out_root。
from smart_mail_agent.cli import e2e_safe as es


def test_injection_helpers(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SMA_ROOT", str(tmp_path))
    monkeypatch.delenv("SMA_EML_DIR", raising=False)
    eml_dir = es.ensure_sample_eml()
    out_root = es.ensure_out_root()
    assert eml_dir.exists() and any(p.suffix == ".eml" for p in eml_dir.iterdir())
    assert out_root.exists()
