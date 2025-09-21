from __future__ import annotations

import importlib
import pathlib
import runpy
import sys
import tempfile
from pathlib import Path

import smart_mail_agent.utils.pdf_safe as pdf_safe

tmpdir = Path(tempfile.mkdtemp())


# 讓 CLI 跑起來且不產生 PDF：先設三參數 stub + Path.home
def _stub3(content, outdir, basename):
    p = Path(outdir) / (basename + ".txt")
    p.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(map(str, content)) if isinstance(content, (list, tuple)) else str(content)
    p.write_text(text, encoding="utf-8")
    return str(p)


pdf_safe.write_pdf_or_txt = _stub3
orig_home = pathlib.Path.home
pathlib.Path.home = lambda: tmpdir  # type: ignore

for argv in (["modules.quotation"], ["modules.quotation", "ACME", "Basic=1x100"]):
    sys.modules.pop("modules.quotation", None)
    bak = sys.argv[:]
    try:
        sys.argv = argv[:]
        try:
            runpy.run_module("modules.quotation", run_name="__main__", alter_sys=True)
        except SystemExit:
            pass
    finally:
        sys.argv = bak

# 還原 home
try:
    pathlib.Path.home = orig_home  # type: ignore
except Exception:
    pass

# 之後才匯入模組，避免覆蓋掉 __main__ 覆蓋率
q = importlib.import_module("modules.quotation")

# 新簽名：怪字元 → 觸發檔名清理
p1 = Path(q.generate_pdf_quote("A?C/ME* 公司", [("Basic", 1, 100.0)], outdir=tmpdir))
assert p1.exists()

# 空項目邊界
p0 = Path(q.generate_pdf_quote("空單", [], outdir=tmpdir))
assert p0.exists()


# 舊簽名（兩參數）→ except TypeError 分支
def _oldsig(content, out_path):
    outp = Path(out_path)
    outp.parent.mkdir(parents=True, exist_ok=True)
    txt = "\n".join(map(str, content)) if isinstance(content, (list, tuple)) else str(content)
    outp.write_text(txt, encoding="utf-8")
    return str(outp)


pdf_safe.write_pdf_or_txt = _oldsig
p2 = Path(q.generate_pdf_quote("ACME2", [("Pro", 2, 50.0)], outdir=tmpdir))
assert p2.exists()

# choose_package：全分支 + 容錯
for subj, body in [
    ("需要 ERP 整合", ""),
    ("", "workflow 自動化"),
    ("附件很大，請協助", ""),
    ("一般詢價", "內容"),
    (None, None),
    ("", ""),
]:
    r = q.choose_package(subject=subj, content=body)
    assert isinstance(r, dict) and "package" in r and "needs_manual" in r
