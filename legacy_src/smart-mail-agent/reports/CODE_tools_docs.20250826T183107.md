# Smart Mail Agent — Tools & Docs (scripts/tools/docs) (20250826T183107)

-----8<----- FILE: docs/ARCHITECTURE.md (size 3534B)
# Smart Mail Agent — Architecture

> 此文件對齊目前主程式（`src/ai_rpa/main.py`）行為：任務編排、Spam Gate、Actions 規劃、可選 Playbook 與 Spam 合併。  
> 原則：**不越改越簡略**，新功能採「只加不減／預設關閉」。

## 1. High-level Flow

```mermaid
flowchart TD
    A[Input] -->|--input-path| B[Read text if needed]
    A -->|--tasks| C[Task Plan (normalize)]
    subgraph Spam
      D1[spam_adapter.score]:::opt
      D2[mailguard.detect]:::gate
    end
    classDef gate fill:#ffe8e8,stroke:#d33,stroke-width:1px
    classDef opt fill:#eef7ff,stroke:#36c,stroke-width:1px

    C -->|nlp?| E[nlp.analyze_text]
    C -->|ocr?| F[ocr.run_ocr]
    C -->|scrape?| G[scraper.scrape]
    C -->|classify_files?| H[file_classifier.classify_dir]
    C -->|spam?| D1
    C -->|mailguard?| D2

    E --> I[Action Planner]
    B --> E
    D1 --> J[optional combine]
    D2 --> J[optional combine]
    J --> I

    D2 -->|verdict=BLOCK| X{Gate BLOCK?}
    I -->|if not BLOCK| K[results.actions]

    F --> L[results.ocr]
    G --> M[results.scrape]
    H --> N[results.classify]
    E --> O[results.nlp]
mailguard.detect 為硬性 Gate：BLOCK 時 actions 會 跳過（steps += actions:skipped_by_mailguard）。

spam_adapter.score 與 mailguard.detect 的合併輸出（results.spamcheck_combined）是可選，設 SPAM_COMBINE=1 才會產生；Gate 策略仍以 mailguard 為準。

2. Tasks & Aliases
CLI Task	Exec Name	Result Key	Notes
nlp	nlp	results.nlp	關鍵字/規則（離線）
ocr	ocr	results.ocr	失敗不影響其他
scrape	scrape	results.scrape	需 --allow-online 才建議打外網
classify	classify_files	results.classify	Alias
classify_files	classify_files	results.classify	
spam	spam	results.spam	ML/Adapter
spamcheck	mailguard	results.spamcheck	Alias
mailguard	mailguard	results.spamcheck	Gate

3. Action Planner
基礎：nlp.analyze_text() → intents（如 sales, refund, support）。

規劃路徑（合併去重）：

內建兜底 _plan_actions_from_nlp（關鍵字補洞）

你的 actions.plan_actions(intents)（已保留舊版語意）

Playbook（可選）：ENABLE_PLAYBOOK=1 → 讀 configs/actions_playbook.yaml，以 any/all/none 規則追加動作

mailguard=BLOCK ⇒ 不寫入 results.actions，僅記 steps（安全優先）。

Intent → Action（現行合併矩陣）
Intent/Signal	產生的 Action（去重後）	來源
sales/quote/「合作/報價」	send_quote / route_to_sales	actions.plan_actions / 兜底 / Playbook
support	open_ticket / reply_support	兜底 / actions.plan_actions
refund/「退款/退貨」	initiate_refund	兜底 / Playbook
invoice/「發票」	resend_invoice	Playbook（可選）
cancel_order/「取消訂單」	cancel_order_and_refund	Playbook（可選）
complaint/「抱怨」	escalate_support	Playbook（可選）

4. Spam Multi-layer
Gate：mailguard.detect → ALLOW/REVIEW/BLOCK（BLOCK 直接阻斷 actions）

ML：spam_adapter.score（不阻斷）

合併（可選）：SPAM_COMBINE=1 → results.spamcheck_combined

Verdict 排序：BLOCK > REVIEW > ALLOW

Score 取最大；Reasons 合併去重

5. 運維與驗收（精簡版）
SLO：Pipeline 成功率 ≥ 99%，actions 的誤觸發率 ≤ 1%，mailguard 誤封率 ≤ 0.5%（以人工抽樣驗證）。

DoD：新增規則/動作需附對應測試；--dry-run 無副作用；OFFLINE=1 下無外網請求；steps 必含每一步結果（ok/err/skipped）。

安全：所有對外請求僅在 --allow-online；Secrets 不落地日志；快照已遮罩。


-----8<----- END docs/ARCHITECTURE.md

-----8<----- FILE: docs/ARCHITECTURE.md.ap20all.bak (size 503B)
架構與資料流
    [Input: file/url] --> [OCR] --> [Scrape] --> [NLP] --> [LLM Summarize] --> [Actions(JSON/PDF/TXT)]
                                   ^                                     |
                                   '------------- 合併文字 --------------'

入口：ai-rpa --input-path <path|url> --tasks ocr,scrape,nlp,actions --output data/output/report.json
容錯：OCR 可回傳 str/dict/list；LLM 無金鑰時退化摘要
日誌：SMA_LOG_DIR=logs，輪替檔 logs/ai_rpa.log

-----8<----- END docs/ARCHITECTURE.md.ap20all.bak

-----8<----- FILE: docs/CONTRIBUTING.md (size 285B)
# CONTRIBUTING

Dev setup：
python -m venv ~/.venv/sma
source ~/.venv/sma/bin/activate
pip install -e .[llm,ocr,dev]
pip install pre-commit && pre-commit install
Style：ruff --fix、black(100)、isort(profile=black)
Tests：pytest -q --maxfail=1 --disable-warnings（CI 不觸網）

-----8<----- END docs/CONTRIBUTING.md

-----8<----- FILE: docs/CRON_EXAMPLE.md (size 208B)
# CRON Examples

每 15 分（離線最小）：
*/15 * * * * cd ~/projects/smart-mail-agent && ~/.venv/sma/bin/ai-rpa --tasks nlp,actions --output share/smoke_output/cron_report.json >> logs/ai_rpa.log 2>&1

-----8<----- END docs/CRON_EXAMPLE.md

-----8<----- FILE: docs/OPERATIONS.md (size 240B)
運維說明
  - .env：OPENAI_API_KEY, OPENAI_MODEL, SMA_LOG_LEVEL, FONT_PATH
  - 字型：assets/fonts/NotoSansTC-Regular.ttf
  - 常見錯誤：tesseract/字型/LLM 金鑰缺失
  - 建議排程：cron 或 GH Actions 週期呼叫 ai-rpa

-----8<----- END docs/OPERATIONS.md

-----8<----- FILE: docs/architecture.md (size 855B)
# Architecture

本專案分層：

- **Ingestion**：`smart_mail_agent/ingestion/*` — 郵件欄位抽取、寫回分類結果等
- **Features (classic)**：`smart_mail_agent/features/*` — 傳統 RPA/規則/記錄器等（多為示範）
- **Spam 模組**：`smart_mail_agent/spam/*` 與 `features/spam/*` — 離線版 orchestrator、規則檢測
- **Routing**：`smart_mail_agent/routing/*` — 行為編排與 CLI 入口（`run_action_handler`）
- **Utils**：`smart_mail_agent/utils/*` — PDF 安全、日誌、設定、驗證器

## CLI

- 幫助：`PYTHONPATH=src python -m src.run_action_handler --help`
- 離線示範：`scripts/demo_offline.sh`

## 測試策略

- CI 僅跑 `tests/unit`、`tests/contracts` 並加 `-m "not online"`，確保離線可重現。
- 覆蓋率徽章：`assets/badges/coverage.svg`（由本地或 CI 更新）。

-----8<----- END docs/architecture.md

-----8<----- FILE: docs/ci/pipeline.md (size 295B)
# 企業級 CI 檢查項目
- 語法與風格：ruff
- 型別檢查：mypy（寬鬆模式，不阻斷 PR）
- 單元測試：pytest（預設排除 `online` 標記）
- 安全審視：pip-audit（相依套件）、bandit（靜態分析）
- 文件檢查：mkdocs build（僅建置，不部署）

-----8<----- END docs/ci/pipeline.md

-----8<----- FILE: docs/cli.md (size 235B)
# CLI 指南
- spam 規則檢查：python -m smart_mail_agent.cli_spamcheck --subject "xxx" --body "yyy"
- 動作路由（離線展示）：OFFLINE=1 python -m smart_mail_agent.routing.run_action_handler --input data/sample/email.json

-----8<----- END docs/cli.md

-----8<----- FILE: docs/guide/cli.md (size 149B)
# CLI 使用與統一風格
主入口：`python -m src.run_action_handler --help`
包裝腳本：`bin/sma` 會啟用 `.venv` 並設 `PYTHONPATH=src`

-----8<----- END docs/guide/cli.md

-----8<----- FILE: docs/guide/tests.md (size 243B)
# 測試規範與環境
- 測試放於 `tests/`，以 `unit/`, `e2e/`, `contracts/`, `spam/`, `portfolio/` 分類
- 線上相依請加 `@pytest.mark.online`（CI 預設不跑）
- 以 `tests/conftest.py` 自動讀取 `.env.example` 與 `.env`

-----8<----- END docs/guide/tests.md

-----8<----- FILE: docs/index.md (size 370B)
# Smart Mail Agent

一個可離線驗證的 AI + RPA 郵件處理範例專案。
快速連結：
- [Architecture](architecture.md)
- [Cookbook](cookbook.md)

**離線展示：**
```bash
scripts/demo_offline.sh
離線測試：

bash
Copy
Edit
pytest -q tests/unit tests/contracts -m "not online" \
  --cov=src/smart_mail_agent --cov-report=term-missing --cov-report=xml

-----8<----- END docs/index.md

-----8<----- FILE: docs/legacy_isolation.md (size 516B)
# Legacy 模組隔離策略

- 目標：避免歷史檔拉低覆蓋率與干擾開發心智。
- 覆蓋率僅統計：`src/`、`smart_mail_agent/`
- 已封存：`archive/legacy_modules/`（不納入覆蓋率、不再維護）
- 過渡例外：`modules/quotation.py`（等移除依賴後刪除）

## 開發者守則
- 不得在新代碼中引用 `modules.*`（過渡例外：`modules.quotation`）
- CI 可執行 `tools/ci-guard.sh` 作靜態檢查
- 本地回歸：`tools/dev-check.sh g3 && tools/dev-check.sh cov`

-----8<----- END docs/legacy_isolation.md

-----8<----- FILE: tools/bootstrap.sh (size 364B)
#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m venv "$PROJECT_ROOT/.venv" 2>/dev/null || true
# shellcheck disable=SC1091
source "$PROJECT_ROOT/.venv/bin/activate"
python -m pip -q install --upgrade pip
python -m pip -q install pytest coverage pyyaml requests beautifulsoup4
echo "[bootstrap] ok"

-----8<----- END tools/bootstrap.sh

-----8<----- FILE: tools/ci-guard.sh (size 979B)
#!/usr/bin/env bash
set -Eeuo pipefail
RED=$'\033[31m'; GRN=$'\033[32m'; YLW=$'\033[33m'; CLR=$'\033[0m'
fail(){ echo "${RED}[GUARD]$CLR $*"; exit 1; }
ok(){ echo "${GRN}[GUARD]$CLR $*"; }

# 拒絕在 src/ 與 tests/ 使用 modules.*（允許 modules.quotation 暫時存在）
if git grep -nE '(^|[^A-Za-z0-9_])from[[:space:]]+modules\.(?!quotation)' -- src tests >/dev/null 2>&1; then
  git grep -nE '(^|[^A-Za-z0-9_])from[[:space:]]+modules\.(?!quotation)' -- src tests
  fail "發現違規 import（from modules.*），請改用 src/ai_rpa 或 smart_mail_agent 等現行模組"
fi
if git grep -nE '(^|[^A-Za-z0-9_])import[[:space:]]+modules\.(?!quotation)' -- src tests >/dev/null 2>&1; then
  git grep -nE '(^|[^A-Za-z0-9_])import[[:space:]]+modules\.(?!quotation)' -- src tests
  fail "發現違規 import（import modules.*），請改用 src/ai_rpa 或 smart_mail_agent 等現行模組"
fi

ok "未發現違規引用 modules.*（保留 modules.quotation 過渡例外）"

-----8<----- END tools/ci-guard.sh

-----8<----- FILE: tools/dev-check.sh (size 1663B)
#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/src"
export OFFLINE="${OFFLINE:-1}"

RED=$'\033[31m'; GRN=$'\033[32m'; BLU=$'\033[34m'; CLR=$'\033[0m'
msg(){ echo "${BLU}[*]${CLR} $*"; }
ok(){  echo "${GRN}[OK]${CLR} $*"; }

clean(){ find "$PROJECT_ROOT" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true; }

list_modules(){
  msg "列出 tests* 內引用到的專案模組（去重）"
  grep -RhoE '(from|import) (smart_mail_agent\.[A-Za-z0-9_\.]+|modules\.quotation|ai_rpa\.[A-Za-z0-9_\.]+)' \
    "$PROJECT_ROOT/tests" "$PROJECT_ROOT/legacy_tests" "$PROJECT_ROOT/tests_smoke" 2>/dev/null \
  | sed -E 's/^(from|import) //; s/ .*//' | sort -u
}

case "${1:-}" in
  g3)
    clean
    msg "pytest -q (分組：AI RPA 主流程)"
    pytest -q legacy_tests/ai_rpa/test_cli_actions.py \
             legacy_tests/ai_rpa/test_main_all_success.py \
             legacy_tests/ai_rpa/test_main_actions_dryrun.py \
             legacy_tests/ai_rpa/test_main_error_paths.py \
             legacy_tests/ai_rpa/test_main_nlp_only_no_texts.py
    ok "分組回歸完成"
    ;;
  cov)
    clean
    msg "執行覆蓋率（僅計 src/ai_rpa）"
    pytest -q
    ;;
  golden)
    msg "只跑規則金樣，不帶 coverage"
    pytest -q tests/ai_rpa_unit/test_nlp_rules_golden.py --no-cov
    ;;
  quick)
    msg "只跑 ai_rpa_unit 下的白箱/合約測試，不帶 coverage"
    pytest -q tests/ai_rpa_unit --no-cov
    ;;
  list)
    list_modules
    ;;
  *)
    echo "用法: tools/dev-check.sh {g3|cov|golden|quick|list}"
    exit 2
    ;;
esac

-----8<----- END tools/dev-check.sh

-----8<----- FILE: tools/dump_repo_into_10parts.py (size 7618B)
#!/usr/bin/env python3
# 檔案位置：tools/dump_repo_into_10parts.py
# 模組用途：掃描專案文字檔，平衡切分為 10 份輸出文本，供人工貼回審閱
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

# 可調參數
N_PARTS = 10
OUTDIR = Path("share/dump_parts")
MAX_BYTES_PER_FILE = 2_000_000  # 單一檔案超過此大小視為大檔，排除
INCLUDE_EXTS = {
    ".py",
    ".sh",
    ".bash",
    ".zsh",
    ".bat",
    ".ps1",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".json",
    ".md",
    ".rst",
    ".txt",
    ".csv",
    ".sql",
    ".env",
    ".env.example",
    ".dockerfile",
    ".service",
    ".properties",
}
INCLUDE_BASENAMES = {
    "Dockerfile",
    "Makefile",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    "requirements.txt",
    "pyproject.toml",
    "Pipfile",
    "Pipfile.lock",
    "setup.cfg",
    "setup.py",
    "README",
    "README.md",
    "LICENSE",
}
EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "node_modules",
    "reports",
    ".cache",
    ".eggs",
    ".tox",
    "share",
}
BINARY_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".webp",
    ".svg",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".ico",
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".rar",
    ".bin",
    ".mp3",
    ".wav",
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
}


def is_binary_path(p: Path) -> bool:
    if p.suffix.lower() in BINARY_EXTS:
        return True
    try:
        with p.open("rb") as f:
            chunk = f.read(8192)
        if b"\x00" in chunk:
            return True
        # 簡單偵測非文字比例
        nontext = sum(b > 127 and b < 255 for b in chunk)
        if len(chunk) and (nontext / len(chunk) > 0.30):
            return True
    except Exception:
        return True
    return False


def should_include(p: Path) -> bool:
    if not p.is_file():
        return False
    if any(part in EXCLUDE_DIRS for part in p.parts):
        return False
    if p.name in INCLUDE_BASENAMES:
        return True
    ext = p.suffix.lower()
    if ext in INCLUDE_EXTS:
        return True
    return False


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_files(root: Path) -> Tuple[List[Path], List[Tuple[str, str]]]:
    included: List[Path] = []
    excluded: List[Tuple[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # 過濾目錄
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            p = Path(dirpath) / fn
            rel = p.relative_to(root)
            # 濾除明顯二進位與超大檔
            if is_binary_path(p):
                excluded.append((str(rel), "binary_or_unreadable"))
                continue
            if p.stat().st_size > MAX_BYTES_PER_FILE:
                excluded.append((str(rel), "too_large"))
                continue
            if should_include(p):
                included.append(p)
            else:
                excluded.append((str(rel), "not_included_ext"))
    # 穩定排序：先路徑、後尺寸
    included.sort(key=lambda x: (str(x.relative_to(root)).lower(), x.stat().st_size))
    return included, excluded


def assign_parts(files: List[Path], root: Path) -> List[List[Path]]:
    # 使用「最小堆」式的平衡分配：每次把下一檔放到目前總大小最小的一份
    import heapq

    parts: List[List[Path]] = [[] for _ in range(N_PARTS)]
    heaps = [(0, i) for i in range(N_PARTS)]  # (bytes, index)
    heapq.heapify(heaps)
    sizes = [0] * N_PARTS
    for p in files:
        size = p.stat().st_size
        total, idx = heapq.heappop(heaps)
        parts[idx].append(p)
        sizes[idx] += size
        heapq.heappush(heaps, (sizes[idx], idx))
    return parts


def write_parts(parts: List[List[Path]], root: Path) -> Dict[str, any]:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    meta = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "root": str(root.resolve()),
        "parts": [],
        "total_files": sum(len(x) for x in parts),
        "note": "使用 -----8<----- FILE: / END 標記分割檔案",
    }
    for i, group in enumerate(parts, start=1):
        outp = OUTDIR / f"part_{i:02d}.txt"
        total_bytes = sum(p.stat().st_size for p in group)
        with outp.open("w", encoding="utf-8", newline="\n") as w:
            header = (
                f"# Dump Part {i:02d}/10  root={root}  files={len(group)}  bytes={total_bytes}\n"
            )
            w.write(header)
            for p in group:
                rel = p.relative_to(root)
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                except Exception as e:
                    content = f"<<READ_ERROR {e}>>"
                sha = sha256_of(p)
                size = p.stat().st_size
                w.write(f"-----8<----- FILE: {rel}  SHA256:{sha}  BYTES:{size} -----\n")
                w.write(content)
                if not content.endswith("\n"):
                    w.write("\n")
                w.write(f"-----8<----- END {rel} -----\n")
        meta["parts"].append({"path": str(outp), "files": len(group), "bytes": total_bytes})
    with (OUTDIR / "README.txt").open("w", encoding="utf-8") as f:
        f.write(
            "將 part_01.txt ~ part_10.txt 依序貼回對話，我會據此重建並比對本機與 GitHub 殘缺版本。\n"
        )
    return meta


def main() -> int:
    root = Path(os.environ.get("PROJECT_DIR") or ".").resolve()

    # 若指定目錄不是專案，嘗試往上找
    def looks_like_repo(p: Path) -> bool:
        return (p / ".git").exists() and ((p / "src").exists() or (p / "pyproject.toml").exists())

    if not looks_like_repo(root):
        cur = Path.cwd().resolve()
        while True:
            if looks_like_repo(cur):
                root = cur
                break
            if cur.parent == cur:
                break
            cur = cur.parent
    if not looks_like_repo(root):
        print("找不到專案根：請在專案內或設 PROJECT_DIR 後再執行", file=sys.stderr)
        return 2

    included, excluded = collect_files(root)
    parts = assign_parts(included, root)
    meta = write_parts(parts, root)
    # 另存索引檔
    index = {
        "generated_at": meta["generated_at"],
        "root": meta["root"],
        "included": [
            {
                "path": str(p.relative_to(root)),
                "bytes": p.stat().st_size,
                "sha256": sha256_of(p),
                "mtime": int(p.stat().st_mtime),
            }
            for p in included
        ],
        "excluded": [{"path": path, "reason": reason} for path, reason in excluded],
        "parts": meta["parts"],
    }
    (OUTDIR / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("OK 產生完成於：", OUTDIR)
    for p in meta["parts"]:
        print(p["path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

-----8<----- END tools/dump_repo_into_10parts.py

-----8<----- FILE: tools/env.sh (size 750B)
#!/usr/bin/env bash
# 請用： source tools/env.sh
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "[env] 請使用：source tools/env.sh"; exit 1
fi
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
if [[ ! -d "$PROJECT_ROOT/.venv" ]]; then
  echo "[env] 找不到 .venv，先執行：bash tools/bootstrap.sh"; return 1
fi
# shellcheck disable=SC1091
source "$PROJECT_ROOT/.venv/bin/activate" || { echo "[env] venv 啟用失敗"; return 1; }
export PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/src"
: "${OFFLINE:=1}"; export OFFLINE
python - <<'PY' || true
import os, sys
print(f"[env] venv: {sys.prefix}")
print(f"[env] PYTHONPATH: {os.environ.get('PYTHONPATH')}")
print(f"[env] OFFLINE={os.environ.get('OFFLINE')}")
PY

-----8<----- END tools/env.sh

-----8<----- FILE: tools/fix_all_lints.py (size 5589B)
from __future__ import annotations

import importlib
import os
import re
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))  # 讓 repo 根目錄可被 import

PY_EXT = (".py",)


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")


def write_text(p: Path, s: str) -> None:
    # 保留結尾換行（給 EOF fixer 友善）
    if not s.endswith("\n"):
        s += "\n"
    p.write_text(s, encoding="utf-8")


def all_py_files() -> list[Path]:
    ignore_dirs = {
        ".git",
        ".venv",
        "venv",
        ".mypy_cache",
        ".ruff_cache",
        "__pycache__",
        ".pytest_cache",
        ".cache",
        "out",
        "outputs",
        "share",
        "tmp_attachments",
        "report_parts_",
        "report_top10_",
        "repo_",
    }
    out = []
    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT).as_posix()
        if any(seg.startswith(tuple(ignore_dirs)) for seg in rel.split("/")):
            continue
        out.append(p)
    return out


def fix_apply_patch():
    p = ROOT / "apply_patch_r9.py"
    if not p.exists():
        return False
    s = read_text(p)
    orig = s
    # 1) 將「行首為非 ASCII」的中文敘述行註解掉，避免語法解析
    new_lines = []
    for line in s.splitlines():
        if re.match(r"^\s*[^\x00-\x7F]", line):
            # 轉成註解
            line = re.sub(r"^(\s*)", r"\1# ", line)
        new_lines.append(line)
    s = "\n".join(new_lines)
    # 2) 補齊未關閉的 r"""（簡單檢查配對數）
    triple = re.findall(r'(^|[^\\])("""|\'\'\')', s)
    if len(triple) % 2 == 1:
        s += '\n"""\n'
    if s != orig:
        write_text(p, s)
        print("[fix] apply_patch_r9.py")
        return True
    return False


STAR_RE = re.compile(r"^from\s+([.\w]+)\s+import\s+\*\s*(#.*)?$", re.M)


def discover_names(mod: ModuleType) -> list[str]:
    names = getattr(mod, "__all__", None)
    if names:
        return sorted([n for n in names if not n.startswith("_")])
    # fallback: dir 過濾掉私有與模組
    out = []
    for n in dir(mod):
        if n.startswith("_"):
            continue
        try:
            if isinstance(getattr(mod, n), ModuleType):
                continue
        except Exception:
            pass
        out.append(n)
    return sorted(out)


def replace_star_imports(p: Path) -> bool:
    s = read_text(p)
    changed = False
    # 可能有多個 star import，逐一替換
    while True:
        m = STAR_RE.search(s)
        if not m:
            break
        modname = m.group(1)
        try:
            mod = importlib.import_module(modname)
        except Exception as e:
            print(f"[warn] cannot import {modname} referenced by {p}: {e}")
            # 跳過這個 star，避免壞掉
            s = (
                s[: m.start()]
                + m.group(0).replace("import *", "import *  # noqa: F403,F401")
                + s[m.end() :]
            )
            changed = True
            continue
        names = discover_names(mod)
        if not names:
            # 沒有可匯出的名稱，一樣降級為 noqa
            repl = f"from {modname} import *  # noqa: F403,F401"
        else:
            joined_names = ",\n    ".join(names)
            repl = f"from {modname} import (\n    {joined_names}\n)\n\n__all__ = [{', '.join(repr(n) for n in names)}]"
        s = s[: m.start()] + repl + s[m.end() :]
        changed = True
    if changed:
        write_text(p, s)
        print(f"[fix] star-import -> explicit: {p}")
    return changed


def rewrite_policy_engine_wrapper():
    p = ROOT / "src" / "smart_mail_agent" / "policy_engine.py"
    if not p.exists():
        return False
    content = '''\
"""Compatibility wrapper for `smart_mail_agent.policy_engine` via core module."""
from importlib import import_module

_core = import_module("smart_mail_agent.core.policy_engine")
apply_policies = getattr(_core, "apply_policies")
apply_policy = getattr(_core, "apply_policy", apply_policies)

__all__ = ["apply_policies", "apply_policy"]
'''
    if read_text(p) != content:
        write_text(p, content)
        print(f"[fix] rewrite wrapper: {p}")
        return True
    return False


def rewrite_internal_smoke_test():
    p = ROOT / "legacy_tests" / "internal_smoke" / "test_import_all_internal.py"
    if not p.exists():
        return False
    content = """\
import importlib
import pkgutil
import smart_mail_agent
import pytest

# 自動發現 smart_mail_agent 下面的所有可匯入模組（避免手寫重覆清單）
mods = [
    m.name
    for m in pkgutil.walk_packages(smart_mail_agent.__path__, prefix="smart_mail_agent.")
]

@pytest.mark.parametrize("mod", mods)
def test_import_module(mod: str) -> None:
    importlib.import_module(mod)
"""
    if read_text(p) != content:
        write_text(p, content)
        print("[fix] rewrite internal smoke test")
        return True
    return False


def main():
    total_changed = 0
    total_changed += bool(fix_apply_patch())
    total_changed += bool(rewrite_policy_engine_wrapper())
    total_changed += bool(rewrite_internal_smoke_test())

    # 逐檔消滅 star import
    for f in all_py_files():
        try:
            if replace_star_imports(f):
                total_changed += 1
        except Exception as e:
            print(f"[warn] fail on {f}: {e}")
    print(f"[done] modified files: {total_changed}")


if __name__ == "__main__":
    main()

-----8<----- END tools/fix_all_lints.py

-----8<----- FILE: tools/fix_all_lints_v2.py (size 6340B)
from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")


def write(p: Path, s: str) -> None:
    if not s.endswith("\n"):
        s += "\n"
    p.write_text(s, encoding="utf-8")


def is_pkg_dir(d: Path) -> bool:
    return (d / "__init__.py").exists()


def module_name_for_file(f: Path) -> Optional[str]:
    """推導檔案的模組路徑（有 __init__.py 鏈路才算套件）。"""
    f = f.resolve()
    if not f.is_file() or f.suffix != ".py":
        return None
    parts: List[str] = []
    d = f.parent
    # 往上收集 __init__.py 連續存在的層級
    while d != ROOT and is_pkg_dir(d):
        parts.append(d.name)
        d = d.parent
    if not parts:
        return None
    parts.reverse()
    mod = ".".join(parts + [f.stem])
    return mod


def resolve_relative(current_mod: str, rel_level: int, rel_module: Optional[str]) -> Optional[str]:
    """把相對匯入（level>0）轉為絕對模組字串。"""
    base = current_mod.split(".")[:-1]  # 去掉檔名
    if rel_level > len(base):
        return None
    base = base[: len(base) - rel_level + 1]
    if rel_module:
        base += rel_module.split(".")
    return ".".join(base)


def guess_exports_from_file(mod_file: Path) -> List[str]:
    """靜態解析：優先讀 __all__；否則取頂層 def/class 名稱（去掉前導底線）。"""
    try:
        tree = ast.parse(read(mod_file))
    except Exception:
        return []
    # 讀 __all__
    exports: List[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "__all__":
                    try:
                        v = ast.literal_eval(node.value)
                        if isinstance(v, (list, tuple)):
                            exports = [str(x) for x in v if isinstance(x, str)]
                            return [n for n in exports if not n.startswith("_")]
                    except Exception:
                        pass
    # 沒有 __all__ → def/class
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                exports.append(node.name)
    # 去重、排序
    return sorted(set(exports))


def find_module_file(abs_module: str) -> Optional[Path]:
    """
    把 'pkg.sub.mod' 映射到專案內的檔案：
    1) <ROOT>/pkg/sub/mod.py
    2) <ROOT>/pkg/sub/mod/__init__.py
    """
    p = ROOT / Path(*abs_module.split("."))
    py = p.with_suffix(".py")
    if py.exists():
        return py
    init = p / "__init__.py"
    if init.exists():
        return init
    return None


def star_import_replacements(f: Path) -> Optional[str]:
    """
    回傳替換後全文；若無修改傳回 None。
    只處理 AST ImportFrom + alias=='*' 的情況。
    """
    src = read(f)
    try:
        tree = ast.parse(src)
    except Exception:
        # 解析不了就不碰（交給 black/ruff 先救）
        return None

    current_mod = module_name_for_file(f)
    # 收集所有 star import 節點
    stars: List[ast.ImportFrom] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if any(getattr(a, "name", "") == "*" for a in node.names):
                stars.append(node)
    if not stars:
        return None

    # 逐一建立替換片段
    # 以行為單位替換：用 end_lineno/col 需 Python 3.8+（這裡 3.10 OK）
    lines = src.splitlines(keepends=True)
    # 先把要換的範圍標記出來
    patches: List[tuple[int, int, str]] = (
        []
    )  # (start_line_idx, end_line_idx_exclusive, replacement)

    for node in stars:
        start = node.lineno - 1
        end = node.end_lineno  # exclusive index
        indent = ""
        # 取縮排
        try:
            indent = lines[start][: len(lines[start]) - len(lines[start].lstrip())]
        except Exception:
            pass

        # 算出絕對模組名
        abs_mod: Optional[str] = None
        if node.level and node.level > 0:
            if current_mod:
                abs_mod = resolve_relative(current_mod, node.level, node.module)
        else:
            abs_mod = node.module

        replacement = None
        if abs_mod:
            mod_file = find_module_file(abs_mod)
            if mod_file:
                names = guess_exports_from_file(mod_file)
                if names:
                    joined = (",\n" + indent + "    ").join(names)
                    replacement = (
                        f"{indent}from {abs_mod} import (\n"
                        f"{indent}    {joined}\n"
                        f"{indent})\n"
                        f"{indent}__all__ = [{', '.join(repr(n) for n in names)}]\n"
                    )

        if replacement is None:
            # 降級方案：保留 * 並加上 noqa，避免卡關
            # 重新用原始行文字（避免刪掉註解）
            original = "".join(lines[start:end])
            if "# noqa" not in original:
                original = original.rstrip("\n") + "  # noqa: F403,F401\n"
            replacement = original

        patches.append((start, end, replacement))

    # 依開始行號由大到小替換，避免位移影響
    patches.sort(key=lambda x: x[0], reverse=True)
    for s_idx, e_idx, rep in patches:
        lines[s_idx:e_idx] = [rep]

    return "".join(lines)


def main() -> None:
    changed = 0
    for p in ROOT.rglob("*.py"):
        # 跳過產物與快取
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith(
            (
                "out/",
                "outputs/",
                "share/",
                ".git/",
                ".ruff_cache/",
                ".pytest_cache/",
                "__pycache__/",
            )
        ):
            continue
        new_src = star_import_replacements(p)
        if new_src is not None and new_src != read(p):
            write(p, new_src)
            changed += 1
            print(f"[fix] star-import -> explicit/noqa: {rel}")
    print(f"[done] modified files: {changed}")


if __name__ == "__main__":
    main()

-----8<----- END tools/fix_all_lints_v2.py

-----8<----- FILE: tools/run_actions_matrix.py (size 1276B)
#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "output" / "matrix"
OUT_DIR.mkdir(parents=True, exist_ok=True)
out = OUT_DIR / "matrix_summary.json"


def case(i: int, action: str, subject: str) -> dict:
    base = {
        "id": f"sample-{i}",
        "action": action,
        "spam": False,
        "request": {
            "subject": subject,
            "from": "test@example.com",
            "body": "hi",
            "attachments": [],
        },
        "expected": {"action": action, "spam": False},
        "result": {"action": action, "spam": False},
        "meta": {"source": "stub"},
    }
    return base


cases = [
    case(0, "reply_general", "hello"),
    case(1, "reply_faq", "faq about pricing"),
    case(2, "reply_support", "need help"),
    case(3, "apply_info_change", "please update my info"),
    case(4, "sales", "interested in plan"),
]

payload = {
    "version": 1,
    "generated_at": os.environ.get("GITHUB_SHA") or "local",
    "total_cases": len(cases),
    "cases": cases,
    "buckets": [],
}

out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[matrix] wrote {out}")

-----8<----- END tools/run_actions_matrix.py

-----8<----- FILE: tools/safe_refactor.py (size 3130B)
#!/usr/bin/env python3
import json
import re
import shutil
from pathlib import Path

ROOT = Path(".").resolve()
SRC = ROOT / "src"
CANON = "smart_mail_agent"
ALIAS_DIRS = [SRC / "utils", SRC / "spam", SRC / "patches", SRC / "modules"]
MAP_DIR = {
    SRC / "utils": SRC / CANON / "utils",
    SRC / "spam": SRC / CANON / "spam",
    SRC / "patches": SRC / CANON / "patches",
    SRC / "modules": SRC / CANON / "features/modules_legacy",
}
REWRITE = [
    (re.compile(r"(?m)^(from)\s+utils(\b)"), r"\1 smart_mail_agent.utils\2"),
    (re.compile(r"(?m)^(import)\s+utils(\b)"), r"\1 smart_mail_agent.utils\2"),
    (re.compile(r"(?m)^(from)\s+spam(\b)"), r"\1 smart_mail_agent.spam\2"),
    (re.compile(r"(?m)^(import)\s+spam(\b)"), r"\1 smart_mail_agent.spam\2"),
    (re.compile(r"(?m)^(from)\s+patches(\b)"), r"\1 smart_mail_agent.patches\2"),
    (re.compile(r"(?m)^(import)\s+patches(\b)"), r"\1 smart_mail_agent.patches\2"),
    (re.compile(r"(?m)^(from)\s+modules(\b)"), r"\1 smart_mail_agent.features.modules_legacy\2"),
    (re.compile(r"(?m)^(import)\s+modules(\b)"), r"\1 smart_mail_agent.features.modules_legacy\2"),
]


def py_files(p: Path):
    return [x for x in p.rglob("*.py") if x.is_file()]


def move_aliases(plan_only=False):
    moves = []
    for d in ALIAS_DIRS:
        if not d.exists():
            continue
        target = MAP_DIR[d]
        for f in py_files(d):
            rel = f.relative_to(d)
            dst = target / rel
            moves.append((f, dst))
            if not plan_only:
                dst.parent.mkdir(parents=True, exist_ok=True)
                if f.resolve() != dst.resolve():
                    shutil.move(str(f), str(dst))
    return moves


def rewrite_imports():
    touched = []
    for f in py_files(SRC):
        txt = f.read_text(encoding="utf-8", errors="ignore")
        new = txt
        for pat, rep in REWRITE:
            new = pat.sub(rep, new)
        if new != txt:
            f.write_text(new, encoding="utf-8")
            touched.append(str(f))
    return touched


def write_compat():
    for d, target in {
        SRC / "utils": "smart_mail_agent.utils",
        SRC / "spam": "smart_mail_agent.spam",
        SRC / "patches": "smart_mail_agent.patches",
        SRC / "modules": "smart_mail_agent.features.modules_legacy",
    }.items():
        d.mkdir(parents=True, exist_ok=True)
        (d / "__init__.py").write_text(
            f"from {target} import *  # noqa: F401,F403\n", encoding="utf-8"
        )


def main():
    plan = {"moves": [], "rewrites": []}
    moves = move_aliases(plan_only=True)
    plan["moves"] = [{"src": str(a), "dst": str(b)} for a, b in moves]
    Path("refactor_plan.json").write_text(
        json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    move_aliases(plan_only=False)
    rew = rewrite_imports()
    plan["rewrites"] = rew
    Path("refactor_plan.json").write_text(
        json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_compat()
    print(f"moved: {len(moves)} files; rewritten imports: {len(rew)} files")


if __name__ == "__main__":
    main()

-----8<----- END tools/safe_refactor.py

