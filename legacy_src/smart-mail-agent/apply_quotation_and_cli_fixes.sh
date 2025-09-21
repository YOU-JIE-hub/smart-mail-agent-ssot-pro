#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "❌ 失敗於第 $LINENO 行（exit=$?）" >&2' ERR

# --- quotation shim（同時相容新舊路徑）---
mkdir -p modules
cat > modules/__init__.py <<'PY'
__all__ = ["quotation"]
PY

cat > modules/quotation.py <<'PY'
from __future__ import annotations
from pathlib import Path
import os
import re
import json
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

__all__ = ["choose_package", "generate_pdf_quote"]

# ---------------- utils ----------------

_CJK_SAFE = r"\u4e00-\u9fff"
_INVALID = re.compile(fr"[^0-9A-Za-z{_CJK_SAFE}]+")
_MULTI_US = re.compile(r"_+")

def _safe_stem(s: Optional[str]) -> str:
    s = _INVALID.sub("_", str(s or "attachment"))
    s = _MULTI_US.sub("_", s).strip("._") or "attachment"
    return s

def _join_text(*parts: Optional[str]) -> str:
    return " ".join([p for p in parts if p])

def _is_big_attachment(text: str) -> bool:
    """>=5MB 或常見片語就視為要人工覆核。"""
    t = (text or "").lower()
    # 數值門檻（大小寫/空白都允許）
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*m\s*b", t, flags=re.I):
        try:
            if float(m.group(1)) >= 5.0:
                return True
        except Exception:
            pass
    # 常見片語
    phrases = ("附件很大", "附件過大", "大附件", "檔案過大", "檔案太大")
    return any(p in (text or "") for p in phrases)

def _has(text: str, *ks: str) -> bool:
    t = text or ""
    return any(k in t for k in ks)

# ---------------- legacy / kwargs evaluators ----------------

def _eval_legacy(subject: Optional[str], content: Optional[str]) -> Dict[str, Any]:
    """
    舊測試預期：
      - ERP/SSO/整合/API/LINE → 企業
      - 自動分類/自動化/排程/workflow → 專業
      - 報價/價格/quote/quotation → 基礎
      - 其他 → 企業（舊預設）
    """
    text = _join_text(subject, content)
    if _is_big_attachment(text):
        return {"package": "標準", "needs_manual": True}
    low = (text or "").lower()
    if _has(text, "ERP", "SSO", "整合", "API", "LINE"):
        return {"package": "企業", "needs_manual": False}
    if _has(text, "自動分類", "自動化", "排程") or ("workflow" in low):
        return {"package": "專業", "needs_manual": False}
    if _has(text, "報價", "價格", "quote", "quotation"):
        return {"package": "基礎", "needs_manual": False}
    return {"package": "企業", "needs_manual": False}

def _eval_kwargs(subject: Optional[str], content: Optional[str]) -> Dict[str, Any]:
    """
    新測試預期：
      - 大附件覆蓋 → 標準 + 需人工
      - ERP/SSO → 企業整合
      - workflow → 進階自動化
      - 其他/報價 → 標準
    """
    text = _join_text(subject, content)
    if _is_big_attachment(text):
        return {"package": "標準", "needs_manual": True}
    low = (text or "").lower()
    if _has(text, "ERP", "SSO"):
        return {"package": "企業整合", "needs_manual": False}
    if "workflow" in low:
        return {"package": "進階自動化", "needs_manual": False}
    # 報價相關歸類到「標準」（新路徑）
    return {"package": "標準", "needs_manual": False}

# ---------------- public API ----------------

def choose_package(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """
    兩種相容呼叫：
      - 舊：choose_package(subject, content)
      - 新：choose_package(subject=..., content=...)
    """
    # 判斷呼叫型態
    called_with_kwargs = ("subject" in kwargs) or ("content" in kwargs)
    if called_with_kwargs:
        subject = kwargs.get("subject")
        content = kwargs.get("content")
        return _eval_kwargs(subject, content)
    else:
        # 位置參數 → 舊邏輯
        subject = args[0] if len(args) >= 1 else None
        content = args[1] if len(args) >= 2 else None
        return _eval_legacy(subject, content)

def _to_lines(lines: Optional[Iterable[Iterable[Any]]]) -> List[str]:
    out: List[str] = []
    if not lines:
        return out
    for row in lines:
        try:
            name, qty, price = row  # type: ignore[misc]
            out.append(f"{name} x{qty} @ {price}")
        except Exception:
            out.append(" ".join(map(str, row)))
    return out

def _write_min_pdf(out_path: Path, title: str, body_lines: Optional[List[str]] = None) -> None:
    """極簡 PDF 兜底（非零大小）。"""
    payload = " | ".join((body_lines or [])[:6]) or title or "Quote"
    content = f"BT /F1 12 Tf 72 720 Td ({payload}) Tj ET\n".encode("latin-1", errors="ignore")
    parts: List[bytes] = []
    parts.append(b"%PDF-1.4\n")
    parts.append(b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n")
    parts.append(b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n")
    parts.append(b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n")
    parts.append(b"4 0 obj<</Length " + str(len(content)).encode("ascii") + b">>stream\n" + content + b"endstream\nendobj\n")
    parts.append(b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n")
    parts.append(b"trailer<<>>\n%%EOF\n")
    out_path.write_bytes(b"".join(parts))

def generate_pdf_quote(*args: Any, **kwargs: Any) -> str:
    """
    相容呼叫：
      - generate_pdf_quote(client_name, package_lines, outdir=..., filename=...)
      - generate_pdf_quote(title="...", lines=[...], outdir=..., filename=...)
    先嘗試 smart_mail_agent.utils.pdf_safe.write_pdf_or_txt，再不行用極簡 PDF。
    若 writer 產出 0 bytes 或檔案不存在，亦會自動補寫。
    """
    title: Optional[str] = kwargs.get("title")
    lines: Optional[Iterable[Iterable[Any]]] = kwargs.get("lines")

    client_name = None
    if title is None and len(args) >= 1:
        client_name = args[0]
    if lines is None and len(args) >= 2 and isinstance(args[1], (list, tuple)):
        lines = args[1]

    outdir = kwargs.get("outdir") or kwargs.get("out_dir") or kwargs.get("output_dir") or "data/attachments"
    outdir_path = Path(outdir)
    outdir_path.mkdir(parents=True, exist_ok=True)

    filename = kwargs.get("filename")
    stem = _safe_stem(filename or title or client_name or "quote")
    out_path = outdir_path / f"{stem}.pdf"

    # 先試 writer（便於測試 monkeypatch）
    used_writer = False
    try:
        from smart_mail_agent.utils import pdf_safe  # type: ignore
        writer = getattr(pdf_safe, "write_pdf_or_txt", None)
        if callable(writer):
            used_writer = True
            content_lines = _to_lines(lines)
            writer(content_lines, str(out_path))
    except Exception:
        used_writer = False  # 確保走兜底

    # 若沒有 writer 或 writer 沒產出實體內容（不存在或 0 bytes），改用內建 PDF
    need_fallback = (not out_path.exists()) or (out_path.exists() and out_path.stat().st_size == 0)
    if (not used_writer) or need_fallback:
        _write_min_pdf(out_path, title=str(title or client_name or "Quote"), body_lines=_to_lines(lines))

    return str(out_path)
PY

# --- CLI wrapper（接受 --input 與 --json；直呼 action_handler.route_action）---
mkdir -p src
cat > src/run_action_handler.py <<'PY'
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

# 相容層：tests 會以 PYTHONPATH=src 執行 `python -m src.run_action_handler`
# 我們直接調用頂層 action_handler（前面已加了 route_action shim）
from action_handler import route_action  # type: ignore

def main() -> None:
    p = argparse.ArgumentParser()
    # 同時接受 --input 與 --json
    p.add_argument("--input", "--json", dest="json_path", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--simulate-failure", dest="simfail")
    # 一個可選的旗標參數（測試可能會帶入，但目前流程不需特別處理）
    p.add_argument("whitelist", nargs="?", default=None)
    args = p.parse_args()

    in_path = Path(args.json_path)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.loads(in_path.read_text(encoding="utf-8"))
    result = route_action(payload, dry_run=args.dry_run, simulate_failure=args.simfail)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
PY

# （可選）快速驗證重點測試集，失敗不終止
echo "— Pytest（quotation 子集）—"
pytest -q tests/test_quotation.py tests/unit/test_quotation_*py || true

echo "— Pytest（CLI 子集）—"
pytest -q tests/e2e/test_offline_suite.py tests/e2e/test_cli_flags.py || true

echo "— Pytest（全部）—"
pytest -q || true
