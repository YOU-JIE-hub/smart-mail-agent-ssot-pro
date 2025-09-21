from ai_rpa.file_classifier import classify_dir


def test_classify_empty_dir(tmp_path):
    out = classify_dir(str(tmp_path))  # 空目錄
    assert out == {"image": [], "pdf": [], "text": [], "other": []}
