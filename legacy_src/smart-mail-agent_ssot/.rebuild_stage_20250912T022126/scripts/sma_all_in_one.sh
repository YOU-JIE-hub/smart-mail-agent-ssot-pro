#!/usr/bin/env bash
set -Eeuo pipefail
umask 022

# --- options ---
PG_URL=""
NO_AUDIT=0
SKIP_TESTS=0
DEBUG=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --pg) PG_URL="$2"; shift 2;;
    --no-audit) NO_AUDIT=1; shift;;
    --skip-tests) SKIP_TESTS=1; shift;;
    --debug) DEBUG=1; shift;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

ts(){ date +"[%Y-%m-%d %H:%M:%S]"; }
log(){ echo "$(ts) $*"; }

# --- preflight: 必須在 WSL Ubuntu + 專案根 ---
if ! uname -a | grep -qi "Linux"; then
  echo "❌ require Linux/WSL shell."; exit 1
fi

# 若不在 repo，嘗試切到既定路徑
if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  if [[ -d "/home/youjie/projects/smart-mail-agent_ssot" ]]; then
    cd /home/youjie/projects/smart-mail-agent_ssot
  fi
fi

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"
if [[ ! -f "pyproject.toml" || ! -d "src/smart_mail_agent" ]]; then
  echo "❌ not in repo root ($ROOT)."; exit 1
fi

# 行尾統一 LF，避免 CRLF 干擾
if compgen -G "scripts/*.sh" >/dev/null; then
  sed -i 's/\r$//' scripts/*.sh || true
fi

# --- 1/9: venv ---
log "[1/9] ensure venv"
if [[ ! -d .venv_clean ]]; then python3 -m venv .venv_clean; fi
# shellcheck disable=SC1091
source .venv_clean/bin/activate
python -m pip -q install -U pip wheel setuptools

# --- 2/9: deps ---
log "[2/9] install base deps"
python -m pip -q install ruff pytest bandit pip-audit \
  sqlalchemy alembic psycopg2-binary \
  langchain-core langchain-community faiss-cpu

# --- 3/9: package layout 保底 ---
log "[3/9] ensure package layout"
mkdir -p src/smart_mail_agent/{cli,rag,rpa/rag,transport,utils,actions}
touch src/smart_mail_agent/__init__.py

# --- 4/9: 離線 Embeddings（若已存在就保留） ---
log "[4/9] write offline Embeddings provider + FAISS builder（不覆蓋現有）"
if [[ ! -f src/smart_mail_agent/rag/provider.py ]]; then
cat > src/smart_mail_agent/rag/provider.py <<'PY'
from __future__ import annotations
import hashlib
from typing import List

try:
    from langchain_core.embeddings import Embeddings  # type: ignore
except Exception:  # pragma: no cover
    class Embeddings:  # type: ignore
        def embed_documents(self, texts: List[str]): ...
        def embed_query(self, text: str): ...

class HashEmb(Embeddings):
    def __init__(self, dim: int = 384) -> None:
        self.dim = dim
    def _vec(self, t: str) -> list[float]:
        b = hashlib.sha1((t or "").encode("utf-8")).digest()
        return [b[i % len(b)] / 255.0 for i in range(self.dim)]
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(x) for x in texts]
    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)
PY
fi

if [[ ! -f src/smart_mail_agent/rag/faiss_build.py ]]; then
cat > src/smart_mail_agent/rag/faiss_build.py <<'PY'
from __future__ import annotations
from pathlib import Path
from typing import Any

try:
    from langchain_community.vectorstores import FAISS  # type: ignore
    from langchain_community.document_loaders import TextLoader  # type: ignore
    from langchain.text_splitter import RecursiveCharacterTextSplitter  # type: ignore
except Exception as e:  # pragma: no cover
    raise SystemExit(f"[rag/faiss_build] Missing langchain community packages: {e}") from e

from .provider import HashEmb

ROOT = Path(".").resolve()
KB_DIR = ROOT / "kb_docs"
OUT = ROOT / "reports_auto" / "kb" / "faiss_index"

def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    if not KB_DIR.exists():
        return {"built": 0, "index": str(OUT), "ok": True}
    texts = []
    for p in KB_DIR.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".txt", ".md"):
            texts.append(TextLoader(str(p), encoding="utf-8").load()[0])
    if not texts:
        return {"built": 0, "index": str(OUT), "ok": True}
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    docs = []
    for d in texts:
        docs += splitter.split_documents([d])
    emb = HashEmb()
    vs = FAISS.from_documents(docs, emb)
    vs.save_local(OUT, index_name="kb")
    return {"built": len(docs), "index": str(OUT), "ok": True}

if __name__ == "__main__":
    import json
    print(json.dumps(build(), ensure_ascii=False))
PY
fi

# --- 5/9: 死信重試 CLI（覆蓋到位） ---
log "[5/9] write Dead-letter retry CLI"
cat > src/smart_mail_agent/cli/retry_dead_letters.py <<'PY'
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
from smart_mail_agent.transport.smtp_send import send_smtp
from smart_mail_agent.utils.config import paths

META = paths().status / "retry_meta.json"

def _load() -> dict[str, Any]:
    return json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}

def _save(d: dict[str, Any]) -> None:
    META.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

def main() -> dict[str, Any]:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=10)
    ap.add_argument("--max_attempts", type=int, default=3)
    args = ap.parse_args()

    P = paths()
    q = P.outbox / "retry"
    q.mkdir(parents=True, exist_ok=True)
    sent = P.outbox / "sent"; sent.mkdir(exist_ok=True)
    dead = P.outbox / "dead"; dead.mkdir(exist_ok=True)

    meta = _load()
    files = sorted(q.glob("*.eml"))[: args.batch]
    retried = 0
    for f in files:
        cnt = int(meta.get(f.name, 0))
        res = send_smtp(f.read_bytes())
        if res.get("sent"):
            (sent / f.name).write_bytes(f.read_bytes())
            f.unlink(missing_ok=True)
            meta.pop(f.name, None)
        else:
            cnt += 1
            if cnt >= args.max_attempts:
                (dead / f.name).write_bytes(f.read_bytes())
                f.unlink(missing_ok=True)
                meta.pop(f.name, None)
            else:
                meta[f.name] = cnt
            retried += 1
    _save(meta)
    out = {"ok": True, "retried": retried, "queue": len(list(q.glob('*.eml')))}
    print(json.dumps(out, ensure_ascii=False))
    return out

if __name__ == "__main__":
    main()
PY

# --- 6/9: CI Gate & PG 腳本（覆蓋到位） ---
log "[6/9] write Enterprise PG script + CI Gate（完整＆最小）"
cat > scripts/sma_ci_security_v3.sh <<'BASH2'
#!/usr/bin/env bash
set -Eeuo pipefail
[[ "${1:-}" == "--debug" ]] && set -x
# shellcheck disable=SC1091
source .venv_clean/bin/activate
export PYTHONPATH="$(git rev-parse --show-toplevel)/src:${PYTHONPATH:-}"
echo "[CI] Ruff fmt check"; ruff format --check src tests
echo "[CI] Ruff lint"; ruff check src tests
echo "[CI] Bandit"; bandit -q -r src -ll
echo "[CI] pip-audit"; pip-audit -q
echo "[CI] pytest"; pytest -q
echo "[CI] OK"
BASH2
chmod +x scripts/sma_ci_security_v3.sh

cat > scripts/sma_ci_security_min.sh <<'BASH3'
#!/usr/bin/env bash
set -Eeuo pipefail
# shellcheck disable=SC1091
source .venv_clean/bin/activate
ruff format --check src tests
ruff check src tests
pytest -q
BASH3
chmod +x scripts/sma_ci_security_min.sh

cat > scripts/sma_enterprise_addons_pg.sh <<'BASH4'
#!/usr/bin/env bash
set -Eeuo pipefail
PG_URL="${1:-${SQLALCHEMY_URL:-}}"
if [[ -z "$PG_URL" ]]; then
  echo "Usage: $0 'postgresql+psycopg2://user:pass@host:5432/dbname'"; exit 2
fi
# shellcheck disable=SC1091
source .venv_clean/bin/activate
export SQLALCHEMY_URL="$PG_URL"
echo "[PG] alembic upgrade head -> $PG_URL"
alembic upgrade head
echo "[PG] done."
BASH4
chmod +x scripts/sma_enterprise_addons_pg.sh

# --- 7/9: 安裝 + 格式化 ---
log "[7/9] project install (editable) + ruff format"
export PYTHONPATH="$ROOT/src:${PYTHONPATH:-}"
python -m pip -q install -e .
ruff check src tests --fix --unsafe-fixes || true
ruff format src tests || true

# --- 8/9: 測試 + 建 KB + 遷移 ---
log "[8/9] tests + build KB + migrations"
python - <<'PY'
from smart_mail_agent.rag.faiss_build import build
import json
print(json.dumps(build(), ensure_ascii=False))
PY

if [[ "$SKIP_TESTS" -eq 0 ]]; then
  pytest -q
else
  echo "[tests] skipped"
fi

if [[ -n "$PG_URL" ]]; then
  bash scripts/sma_enterprise_addons_pg.sh "$PG_URL"
else
  echo "[sqlite] stamp head（不動已存在表）"
  alembic stamp head || true
fi

# --- 9/9: 完成 ---
log "[9/9] all done."
cat <<'MSG'
Quick commands:
  # 死信重試
  python -m smart_mail_agent.cli.retry_dead_letters --batch 10 --max_attempts 3

  # 本地 CI Gate（完整 / 最小）
  bash scripts/sma_ci_security_v3.sh --debug
  bash scripts/sma_ci_security_min.sh

  # 企業 PG 遷移
  bash scripts/sma_enterprise_addons_pg.sh 'postgresql+psycopg2://user:pass@host:5432/dbname'
MSG
