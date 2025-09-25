from ai_rpa.file_classifier import classify_dir


def test_classify_dir(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "b.PDF").write_bytes(b"x")
    (tmp_path / "c.txt").write_text("x", encoding="utf-8")
    (tmp_path / "d.bin").write_bytes(b"x")
    out = classify_dir(str(tmp_path))
    assert (
        len(out["image"]) == 1
        and len(out["pdf"]) == 1
        and len(out["text"]) == 1
        and len(out["other"]) == 1
    )


def test_classify_dir_missing(tmp_path):
    out = classify_dir(str(tmp_path / "nope"))
    assert out == {"image": [], "pdf": [], "text": [], "other": []}
