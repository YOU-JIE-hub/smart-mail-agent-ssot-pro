import json
import subprocess
import sys
from pathlib import Path

PR = Path(__file__).resolve().parents[1]
OUT = PR / "data" / "output"
SAMPLES = PR / "samples"


def _run(cmd):
    p = subprocess.run(cmd, cwd=PR, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr or p.stdout


def test_nlp_to_json():
    OUT.mkdir(parents=True, exist_ok=True)
    _run(
        [
            sys.executable,
            "-m",
            "ai_rpa.main",
            "--input-path",
            str(SAMPLES / "nlp_demo.txt"),
            "--tasks",
            "nlp,actions",
            "--output",
            str(OUT / "report.json"),
        ]
    )
    j = json.loads(Path(OUT / "report.json").read_text(encoding="utf-8"))
    assert j.get("ok") is True and "artifacts" in j


def test_ocr_skip_if_no_lang():
    try:
        import pytesseract

        langs = set(pytesseract.get_languages(config=""))
    except Exception:
        return  # 無 tesseract 視為跳過
    if not ({"chi_tra", "osd", "eng"} & langs):
        return  # 未裝中文語言包視為跳過
    OUT.mkdir(parents=True, exist_ok=True)
    _run(
        [
            sys.executable,
            "-m",
            "ai_rpa.main",
            "--input-path",
            str(SAMPLES / "ocr_tra.png"),
            "--tasks",
            "ocr,actions",
            "--output",
            str(OUT / "ocr_report.json"),
        ]
    )
    j = json.loads(Path(OUT / "ocr_report.json").read_text(encoding="utf-8"))
    assert j.get("ok") is True
