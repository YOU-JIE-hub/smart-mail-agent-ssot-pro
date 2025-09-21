from ai_rpa.file_classifier import classify_dir


def test_classify_dir_with_nested_dir(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "x.md").write_text("x", encoding="utf-8")
    (tmp_path / "y.bin").write_bytes(b"x")
    out = classify_dir(str(tmp_path))
    # 應同時包含 text 與 other；遇到子資料夾要能正常 continue
    assert any(p.endswith("x.md") for p in out["text"])
    assert any(p.endswith("y.bin") for p in out["other"])
