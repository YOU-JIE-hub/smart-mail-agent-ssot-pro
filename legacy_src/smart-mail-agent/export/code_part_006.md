# Project Code Export (Part 006/010)

## scripts/upgrade_enterprise_plan.sh  
```bash
#!/usr/bin/env bash
# 文件: scripts/upgrade_enterprise_plan.sh
# 目的: 一鍵、安全、可重複的原子補丁（不改名、不搬家、不污染）
# 參數: RUN_TESTS=1  -> 補丁後立刻跑 pytest
#      CHECK_ONLY=1 -> 只檢查不寫檔（乾跑）
#      VERBOSE=1    -> 顯示更多偵錯訊息
set -Eeuo pipefail
set -o errtrace
trap 'echo "[FAIL] line=\$LINENO, cmd=\$BASH_COMMAND, code=\$?" >&2' ERR

log(){ printf '%s\n' "$*"; }
fail(){ printf '[FAIL] %s\n' "$*" >&2; exit 96; }

guess_root() {
  # 1) git root
  if command -v git >/dev/null 2>&1; then
    local gr; gr="$(git rev-parse --show-toplevel 2>/dev/null || true)"
    if [[ -n "$gr" && -f "$gr/src/ai_rpa/main.py" ]]; then printf '%s' "$gr"; return; fi
  fi
  # 2) 往上找 .git + src/ai_rpa/main.py
  local c d; c="$(pwd)"
  while :; do
    if [[ -d "$c/.git" && -f "$c/src/ai_rpa/main.py" ]]; then printf '%s' "$c"; return; fi
    d="$(dirname "$c")"; [[ "$d" == "$c" ]] && break; c="$d"
  done
  # 3) 從 PYTHONPATH 嘗試
  IFS=: read -r -a pp <<< "${PYTHONPATH:-}"
  for p in "${pp[@]}"; do
    [[ -z "$p" ]] && continue
    if [[ -f "$p/ai_rpa/main.py" ]]; then printf '%s' "$(dirname "$p")"; return; fi
    if [[ -f "$p/src/ai_rpa/main.py" ]]; then printf '%s' "$p"; return; fi
  done
  # 4) 已知快照路徑
  for p in "$HOME/projects/smart-mail-agent" "/home/youjie/projects/smart-mail-agent"; do
    [[ -f "$p/src/ai_rpa/main.py" ]] && { printf '%s' "$p"; return; }
  done
  printf ''
}

ROOT="${ROOT:-$(guess_root)}"
[[ -n "$ROOT" ]] || fail "找不到專案根（需含 .git 與 src/ai_rpa/main.py）"
cd "$ROOT"

[[ "${VERBOSE:-0}" == "1" ]] && set -x
log "[INFO] Project root = $ROOT"
[[ -d ".git" ]] || fail "不是專案根（無 .git）"
[[ -f "src/ai_rpa/main.py" ]] || fail "找不到 src/ai_rpa/main.py"

TS="$(date +%Y%m%dT%H%M%S)"
mkdir -p reports docs/flow src/ai_rpa/utils data
DIFF="reports/ATOMIC_PATCH.${TS}.diff"; : > "$DIFF"

backup(){ [[ -f "$1" ]] && cp -f "$1" "$1.bak.${TS}" && log "[BACKUP] $1 -> $1.bak.${TS}" || true; }
backup src/ai_rpa/main.py
backup .env.example

# ============ DB 模組：若不存在才寫入 ============
DBMOD="src/ai_rpa/utils/db.py"
if [[ ! -f "$DBMOD" && "${CHECK_ONLY:-0}" != "1" ]]; then
  cat > "$DBMOD" <<'PY'
from __future__ import annotations
import os, sqlite3, json, time
from pathlib import Path
from typing import Any, Dict, List
__all__ = ["persist_run_if_enabled"]

def _db_path() -> Path:
    p = os.getenv("SMA_DB_PATH", "data/sma.db")
    path = Path(p); path.parent.mkdir(parents=True, exist_ok=True); return path

def _connect() -> sqlite3.Connection: return sqlite3.connect(str(_db_path()))

def _migrate(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS runs(
        run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, tasks TEXT, unknown TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS inbound_messages(
        msg_id TEXT PRIMARY KEY, run_id TEXT, input_path TEXT, text_length INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS spam_checks(
        run_id TEXT, source TEXT, verdict TEXT, score REAL, reasons TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS action_plans(
        run_id TEXT, action TEXT, reason TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS errors(run_id TEXT, message TEXT)""")
    conn.commit()

def _as_list(x: Any) -> List[Any]:
    if isinstance(x, list): return x
    return [x] if x is not None else []

def persist_run_if_enabled(out: Dict[str, Any], input_path: str | None = None, text_length: int | None = None) -> None:
    if os.getenv("SMA_DB_ENABLE", "0") not in {"1","true","TRUE"}: return
    conn = _connect(); _migrate(conn); cur = conn.cursor()
    run_id = f"run-{int(time.time()*1000)}"
    cur.execute("INSERT OR REPLACE INTO runs(run_id,created_at,tasks,unknown) VALUES(?,?,?,?)",
        (run_id, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         json.dumps(_as_list(out.get('tasks')), ensure_ascii=False),
         json.dumps(_as_list(out.get('unknown')), ensure_ascii=False)))
    cur.execute("INSERT OR REPLACE INTO inbound_messages(msg_id,run_id,input_path,text_length) VALUES(?,?,?,?)",
        (f"msg-{run_id}", run_id, input_path or "", int(text_length or 0)))
    res = out.get("results", {}) or {}
    def _ins_spam(key: str, source: str):
        r = res.get(key) or {}
        if isinstance(r, dict):
            cur.execute("INSERT INTO spam_checks(run_id,source,verdict,score,reasons) VALUES(?,?,?,?,?)",
                (run_id, source, str(r.get("verdict") or ""), float(r.get("score") or 0.0),
                 json.dumps(_as_list(r.get("reasons")), ensure_ascii=False)))
    _ins_spam("spam", "spam"); _ins_spam("spamcheck", "mailguard"); _ins_spam("spamcheck_combined", "combined")
    for a in _as_list(res.get("actions")):
        if isinstance(a, dict):
            cur.execute("INSERT INTO action_plans(run_id,action,reason) VALUES(?,?,?)",
                (run_id, str(a.get("action") or ""), str(a.get("reason") or "")))
        else:
            cur.execute("INSERT INTO action_plans(run_id,action,reason) VALUES(?,?,?)", (run_id, str(a), "legacy"))
    for e in _as_list(out.get("errors")):
        cur.execute("INSERT INTO errors(run_id,message) VALUES(?,?)", (run_id, str(e)))
    conn.commit(); conn.close()
PY
  log "[WRITE] $DBMOD"
else
  log "[KEEP] $DBMOD 已存在或 CHECK_ONLY=1"
fi

# ============ 修補 main.py（錨點找不到會降級到 print(payload) 前） ============
python3 - "$TS" "${CHECK_ONLY:-0}" <<'PY'
import re, sys, os
from pathlib import Path
ts = sys.argv[1]; check_only = sys.argv[2] == "1"
p = Path("src/ai_rpa/main.py"); s = p.read_text(encoding="utf-8")
changed = False

def insert_before_printpayload(src, block):
    for pat in [r"\n\s*print\(\s*payload\s*\)", r"payload\s*=\s*json\.dumps\(", r"\n\s*return\s+"]:
        m = re.search(pat, src)
        if m: return src[:m.start()] + block + src[m.start():], True
    return src + "\n" + block, True

# 1) import db hook
if "persist_run_if_enabled" not in s:
    s = s.replace(
        "\nimport ai_rpa.mailguard.detector as mailguard_detector\n",
        "\nimport ai_rpa.mailguard.detector as mailguard_detector\n"
        "try:\n"
        "    from ai_rpa.utils.db import persist_run_if_enabled  # type: ignore\n"
        "except Exception:\n"
        "    def persist_run_if_enabled(*a, **k):\n"
        "        return None\n"
    ); changed = True

# 2) spam variables
if "spam_ml = None" not in s:
    s = s.replace("spam_verdict = None", "spam_verdict = None\n    spam_ml = None\n    spam_guard = None"); changed = True

# 3) actions + spam combine block
block = (
    "\n    # 規劃 actions（融合 _plan_actions / ai_rpa.actions / Playbook；Gate=ALLOW 才輸出）\n"
    "    if any(exe == \"actions\" for _, exe in exec_plan):\n"
    "        try:\n"
    "            intents_for_actions = []\n"
    "            if \"nlp\" in out.get(\"results\", {}):\n"
    "                intents_for_actions = list(out[\"results\"][\"nlp\"].get(\"intents\") or [])\n"
    "            text_for_plan = text_cache or \"\"\n"
    "            if spam_verdict is None or spam_verdict == \"ALLOW\":\n"
    "                base_plan = _plan_actions_from_nlp(list(intents_for_actions), text_for_plan)\n"
    "                try:\n"
    "                    from ai_rpa.actions import plan_actions as _pa\n"
    "                    for a in _pa(intents_for_actions, dry_run=dry_run):\n"
    "                        base_plan.append({\"action\": str(a), \"reason\": \"plan_actions\"})\n"
    "                except Exception:\n"
    "                    pass\n"
    "                try:\n"
    "                    enable_playbook = bool(int(os.getenv(\"ENABLE_PLAYBOOK\", \"0\")))\n"
    "                except Exception:\n"
    "                    enable_playbook = False\n"
    "                if enable_playbook and (load_playbook and plan_with_playbook):\n"
    "                    pb = load_playbook(os.getenv(\"PLAYBOOK_PATH\", \"configs/actions_playbook.yaml\"))\n"
    "                    for a in (plan_with_playbook(intents_for_actions, pb) or []):\n"
    "                        base_plan.append({\"action\": str(a), \"reason\": \"playbook\"})\n"
    "                final, seen = [], set()\n"
    "                for it in base_plan:\n"
    "                    a = str((it or {}).get(\"action\", \"\")).strip()\n"
    "                    if a and a not in seen:\n"
    "                        seen.add(a); final.append({\"action\": a, \"reason\": (it or {}).get(\"reason\", \"\")})\n"
    "                out.setdefault(\"results\", {})[\"actions\"] = final\n"
    "                out[\"steps\"].append(\"actions:ok\")\n"
    "            else:\n"
    "                out[\"steps\"].append(\"actions:skipped_by_mailguard\")\n"
    "        except Exception as e:\n"
    "            out[\"errors\"].append(f\"actions: {e!r}\")\n"
    "            out[\"steps\"].append(\"actions:err\")\n"
    "\n"
    "    # 可選：Spam 合併（SPAM_COMBINE=1）\n"
    "    if os.getenv(\"SPAM_COMBINE\", \"0\") == \"1\":\n"
    "        def _rank(v): return {\"BLOCK\":2,\"REVIEW\":1,\"ALLOW\":0}.get(str(v).upper(),0)\n"
    "        sources = [x for x in (locals().get(\"spam_ml\"), locals().get(\"spam_guard\")) if isinstance(x, dict)]\n"
    "        if sources:\n"
    "            best = max(sources, key=lambda r: _rank(r.get(\"verdict\")))\n"
    "            merged = {\"verdict\": best.get(\"verdict\",\"ALLOW\"),\n"
    "                      \"score\": max((float(r.get(\"score\") or 0.0) for r in sources), default=0.0),\n"
    "                      \"reasons\": []}\n"
    "            seen=set()\n"
    "            for r in sources:\n"
    "                for rr in (r.get(\"reasons\") or []):\n"
    "                    if rr not in seen:\n"
    "                        seen.add(rr); merged[\"reasons\"].append(rr)\n"
    "            out.setdefault(\"results\", {})[\"spamcheck_combined\"] = merged\n"
    "            out[\"steps\"].append(\"spamcheck_combined:ok\")\n"
)
m = re.search(r"(# 規劃 actions（如果在任務中）[\\s\\S]*?)# 輸出：--dry-run", s)
if m:
    s = s[:m.start()] + block + "\n    # 輸出：--dry-run" + s[m.end():]; changed = True
else:
    s, c2 = insert_before_printpayload(s, block + "\n"); changed = changed or c2

# 4) 在 payload 序列化前呼叫 DB（若未加入）
if "persist_run_if_enabled(out" not in s:
    s = s.replace(
        "payload = json.dumps(out, ensure_ascii=False)",
        "payload = json.dumps(out, ensure_ascii=False)\n"
        "    try:\n"
        "        _text_len = len(text_cache or \"\") if isinstance(text_cache, (str, type(None))) else 0\n"
        "        persist_run_if_enabled(out, getattr(ns, 'input_path', None), _text_len)\n"
        "    except Exception:\n"
        "        pass\n"
    ); changed = True

if changed and not check_only:
    p.write_text(s, encoding="utf-8"); print("[PATCH] src/ai_rpa/main.py")
else:
    print("[SKIP] src/ai_rpa/main.py 已是最新或 CHECK_ONLY=1")
PY

# ============ .env.example 追加 DB 設定 ============
if [[ -f ".env.example" && "${CHECK_ONLY:-0}" != "1" ]]; then
  if ! grep -q "^SMA_DB_ENABLE=" .env.example; then
    { echo ""; echo "# DB（預設關閉；設 1 啟用 SQLite 紀錄）"; echo "SMA_DB_ENABLE=0"; echo "SMA_DB_PATH=data/sma.db"; } >> .env.example
    log "[WRITE] .env.example (+SMA_DB_*)"
  else
    log "[KEEP] .env.example 已含 SMA_DB_*"
  fi
fi

# ============ Mermaid 流程圖 ============
if [[ "${CHECK_ONLY:-0}" != "1" ]]; then
cat > "docs/flow/ai_rpa_pipeline.mmd" <<'MERMAID'
flowchart TD
  A[輸入] -->|--tasks 解析| B[任務標準化]
  A -->|--input-path| C[讀取文字快取]
  subgraph SPAM[Spam 多層]
    D1[spam_adapter.score (ML)]
    D2[mailguard.detect (Gate)]
  end
  C --> NLP[nlp.analyze_text 規則/關鍵字]
  B -->|包含 spam?| D1
  B -->|包含 mailguard?| D2
  NLP --> PLAN[行為規劃融合]
  D1 --> FUSE[可選合併 spamcheck_combined]
  D2 --> FUSE
  FUSE -->|BLOCK/REVIEW → 跳過| SKIP[actions:skipped_by_mailguard]
  PLAN --> ACTS[results.actions]
  subgraph PLAN[行為規劃融合]
    P1[_plan_actions_from_nlp]
    P2[ai_rpa.actions.plan_actions]
    P3[Playbook(ENABLE_PLAYBOOK)]
  end
  P1 --> MERGE
  P2 --> MERGE
  P3 --> MERGE
  MERGE -->|去重保序| ACTS
  B -->|包含 ocr?| OCR[OCR]
  B -->|包含 scrape?| SCRAPE[Scraper]
  B -->|包含 classify?| CLASSIFY[檔案分類]
  ACTS --> OUT[輸出 JSON / 落 DB(可選)]
MERMAID
  log "[WRITE] docs/flow/ai_rpa_pipeline.mmd"
fi

# ============ diff ============
for f in src/ai_rpa/main.py .env.example; do
  [[ -f "$f.bak.${TS}" ]] && diff -u "$f.bak.${TS}" "$f" || true
done >> "$DIFF" || true
log "[DIFF] $DIFF"

# ============ 測試 ============
if [[ "${RUN_TESTS:-0}" == "1" ]]; then
  log "[INFO] RUN_TESTS=1 → pytest -q"
  pytest -q || fail "pytest 有失敗，請查看輸出"
  log "[OK] pytest 全綠"
fi

log "[OK] 完成。若要只檢查不寫檔：CHECK_ONLY=1 bash scripts/upgrade_enterprise_plan.sh"

```

## src/smart_mail_agent/actions/sales_inquiry.py  
```python
from __future__ import annotations

import json

#!/usr/bin/env python3
# 檔案位置：src/actions/sales_inquiry.py
# 模組用途：處理商務詢問；抽取關鍵欄位並以模板產出需求彙整 .md 附件；補充 meta.next_step
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except Exception:
    Environment = None  # type: ignore

ACTION_NAME = "sales_inquiry"


def _ensure_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def _load_template_env() -> Environment | None:
    """
    嘗試從 templates/ 與 src/templates/ 建立 Jinja2 環境
    """
    if Environment is None:
        return None
    search_paths: list[str] = []
    for d in ("templates", "src/templates"):
        if Path(d).is_dir():
            search_paths.append(d)
    if not search_paths:
        return None
    return Environment(
        loader=FileSystemLoader(search_paths),
        autoescape=select_autoescape(enabled_extensions=("j2", "html", "md")),
        enable_async=False,
    )


# 規則式抽取：公司、數量、截止、預算、關鍵詞
RE_COMPANY = re.compile(
    r"([A-Za-z\u4e00-\u9fa5][\w\u4e00-\u9fa5＆&\.-]{1,30})(?:股份有限公司|有限公司|公司)",
    re.I,
)
RE_QUANTITY = re.compile(r"(\d{1,6})\s*(台|件|個|套|pcs?)", re.I)
RE_BUDGET = re.compile(r"(?:NTD?|新台幣|\$)\s*([0-9][0-9,]{0,12})(?:\s*(萬|千|元|dollars?))?", re.I)
RE_DATE1 = re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})")  # YYYY-MM-DD
RE_DATE2 = re.compile(r"(\d{1,2})[月/](\d{1,2})[日]?", re.I)  # M月D日 or M/D
RE_KEYWORDS = re.compile(r"[A-Za-z\u4e00-\u9fa5]{2,15}")

COMMON_STOP = {
    "我們",
    "你好",
    "您好",
    "謝謝",
    "請問",
    "協助",
    "需要",
    "希望",
    "聯繫",
    "安排",
    "報價",
    "需求",
    "規格",
    "提供",
}


def _extract_fields(subject: str, body: str, sender: str | None) -> dict[str, Any]:
    text = f"{subject}\n{body}"
    company = None
    m = RE_COMPANY.search(text)
    if m:
        company = m.group(0)

    quantity = None
    m = RE_QUANTITY.search(text)
    if m:
        quantity = f"{m.group(1)}{m.group(2)}"

    budget = None
    m = RE_BUDGET.search(text)
    if m:
        money = m.group(1).replace(",", "")
        unit = m.group(2) or "元"
        budget = f"{money}{unit}"

    deadline = None
    m = RE_DATE1.search(text)
    if m:
        yyyy, mm, dd = m.groups()
        deadline = f"{yyyy}-{int(mm):02d}-{int(dd):02d}"
    else:
        m = RE_DATE2.search(text)
        if m:
            # 以當年補齊
            year = datetime.now().year
            mm, dd = m.groups()
            deadline = f"{year}-{int(mm):02d}-{int(dd):02d}"

    kw_raw = [w for w in RE_KEYWORDS.findall(text) if w not in COMMON_STOP]
    keywords = []
    seen = set()
    for w in kw_raw:
        if w.lower() in seen:
            continue
        seen.add(w.lower())
        keywords.append(w)
        if len(keywords) >= 8:
            break

    contact = None
    if sender and "@" in sender:
        contact = sender.split("@", 1)[0]

    summary = subject.strip()[:120]

    return {
        "company": company,
        "quantity": quantity,
        "deadline": deadline,
        "budget": budget,
        "keywords": keywords,
        "contact": contact,
        "summary": summary,
    }


def _render_needs_md(context: dict[str, Any]) -> str:
    env = _load_template_env()
    if env:
        try:
            tpl = env.get_template("needs_summary.md.j2")
            return tpl.render(**context)
        except Exception:
            pass
    # 簡單回退
    ks = ", ".join(context.get("keywords") or [])
    return (
        "# 商務需求彙整\n\n"
        f"- 公司：{context.get('company') or '未明'}\n"
        f"- 聯絡人：{context.get('contact') or '未明'}\n"
        f"- 需求摘要：{context.get('summary') or '未提供'}\n\n"
        "## 關鍵欄位\n"
        f"- 數量：{context.get('quantity') or '未明'}\n"
        f"- 截止：{context.get('deadline') or '未明'}\n"
        f"- 預算：{context.get('budget') or '未明'}\n"
        f"- 關鍵字：{ks or '無'}\n\n"
        "## 建議下一步\n"
        "1. 由業務與對方確認功能範圍與驗收標準\n"
        "2. 安排需求澄清會議並產出會議紀要\n"
        "3. 依會議結論繪製最小可行方案並給出時程與成本\n"
    )


def execute(request: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    參數:
        request: 輸入 JSON（subject/from/body/predicted_label/confidence/attachments）
        context: 可選上下文
    回傳:
        ActionResult dict：含 .md 附件與 meta.next_step
    """
    subject = str(request.get("subject") or "").strip()
    body = str(request.get("body") or "").strip()
    sender = request.get("from")

    req_id = (request.get("meta") or {}).get("request_id") or uuid.uuid4().hex[:12]
    fields = _extract_fields(subject, body, sender)
    md_text = _render_needs_md(fields)

    out_dir = Path("data/output")
    _ensure_dir(out_dir)
    md_name = f"needs_summary_{req_id}.md"
    md_path = out_dir / md_name
    md_path.write_text(md_text, encoding="utf-8")

    attachments = request.get("attachments") or []
    attachments = list(attachments)
    try:
        size = md_path.stat().st_size
    except Exception:
        size = len(md_text.encode("utf-8"))

    attachments.append({"filename": md_name, "size": size})

    meta = dict(request.get("meta") or {})
    meta.update(
        {
            "next_step": "安排需求澄清會議並由業務跟進",
            "confidence": request.get("confidence"),
            "request_id": req_id,
        }
    )

    return {
        "action_name": ACTION_NAME,
        "subject": "[自動回覆] 商務詢問回覆",
        "body": "您好，已收到您的商務需求，附件為彙整內容，將由業務與您聯繫確認細節。",
        "attachments": attachments,
        "meta": meta,
    }


# 兼容不同呼叫名稱
handle = execute
run = execute

if __name__ == "__main__":
    import json
    import sys

    payload = json.loads(sys.stdin.read() or "{}")
    print(json.dumps(execute(payload), ensure_ascii=False))

```

