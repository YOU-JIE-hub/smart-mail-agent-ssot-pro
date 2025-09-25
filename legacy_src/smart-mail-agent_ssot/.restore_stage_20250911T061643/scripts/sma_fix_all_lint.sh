#!/usr/bin/env bash
set -Eeuo pipefail
umask 022
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

# 0) Ruff 設定：保留 120 欄寬、忽略 E501（line-too-long），其餘嚴格
cat > .ruff.toml <<'TOML'
line-length = 120
target-version = "py310"

[lint]
select = ["E","F","W","I","UP","B","A","C4"]
ignore = ["E501"]
fixable = ["ALL"]
TOML

###############################################################################
# 1) pipeline/pipe_run.py  — 重寫，去除 E401/E701/E702/UP035/B…，介面不變
###############################################################################
cat > src/smart_mail_agent/pipeline/pipe_run.py <<'PY'
from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from typing import Any

from smart_mail_agent.actions.router import route
from smart_mail_agent.ingest.eml_dir import load_dir
from smart_mail_agent.ingest.imap_pull import pull_imap
from smart_mail_agent.ml import infer
from smart_mail_agent.policy.engine import apply_policies
from smart_mail_agent.utils.config import paths
from smart_mail_agent.utils.crash import crash_dump
from smart_mail_agent.utils.logger import time_ms


def _ts() -> str:
    return time.strftime("%Y%m%dT%H%M%S")


def gate(xs: list[dict[str, Any]]) -> dict[str, int]:
    d: dict[str, int] = {"done": 0, "error": 0, "queued": 0}
    for a in xs:
        st = a.get("status", "queued")
        d[st] = d.get(st, 0) + 1
    for k in ("done", "error", "queued"):
        d.setdefault(k, 0)
    return d


def _ensure_samples(p) -> None:
    samples = p.root / "samples" / "inbox"
    samples.mkdir(parents=True, exist_ok=True)
    if any(samples.glob("*.txt")):
        return
    ss = [
        "您好，想詢問上一張報價是否還有效？",
        "我要查詢貨件的追蹤號碼，謝謝。",
        "請問可否開立發票抬頭為 AAA？",
        "前次詢價，是否可提供折扣與交期？",
    ]
    for i, t in enumerate(ss, 1):
        (samples / f"mail_{i:02d}.txt").write_text(t, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", choices=["samples", "dir", "imap"], default="samples")
    ap.add_argument("--dir", default=None)
    args = ap.parse_args()

    p = paths()
    _ensure_samples(p)

    if args.inbox == "samples":
        mails = load_dir(str(p.root / "samples" / "inbox"))
    elif args.inbox == "dir":
        mails = load_dir(args.dir or str(p.root / "samples" / "inbox"))
    else:
        cfg = {
            "host": os.getenv("IMAP_HOST"),
            "port": os.getenv("IMAP_PORT"),
            "user": os.getenv("IMAP_USER"),
            "pass": os.getenv("IMAP_PASS"),
            "ssl": os.getenv("IMAP_SSL", "1") == "1",
            "mailbox": os.getenv("IMAP_MAILBOX", "INBOX"),
        }
        mails = pull_imap(cfg)

    actions: list[dict[str, Any]] = []
    for m in mails[:10]:
        t0 = time_ms()
        try:
            sp = infer.predict_spam(m["body"])
            if sp.get("label") == "spam":
                actions.append(
                    {
                        "id": m["id"],
                        "status": "done",
                        "spam": sp,
                        "intent": {"intent": "spam", "score": sp["score"], "needs_review": False, "top2": []},
                        "kie": {"ok": True, "fields": {}, "coverage": {}},
                        "artifacts": [],
                        "outbox": [],
                        "alerts": [{"level": "low", "message": "spam filtered"}],
                        "tickets": [],
                        "latency_ms": time_ms() - t0,
                        "ts": _ts(),
                    }
                )
                continue

            it = infer.predict_intent(m["body"])
            kie = (
                infer.extract_kie(m["body"])
                if it.get("intent") in {"quote", "order", "invoice", "logistics", "warranty", "general"}
                else {"ok": True, "fields": {}, "coverage": {}}
            )
            pol = apply_policies(
                {"mail": m, "intent": it.get("intent"), "kie": kie, "intent_score": it.get("score", 0.0)}
            )
            act = route(m, it.get("intent"), kie)
            actions.append(
                {
                    "id": m["id"],
                    "status": "done",
                    "spam": sp,
                    "intent": it,
                    "kie": kie,
                    "alerts": pol.get("alerts", []),
                    "tickets": pol.get("tickets", []),
                    "artifacts": act.get("artifacts", []),
                    "outbox": act.get("outbox", []),
                    "needs_review": it.get("needs_review") or act.get("needs_review"),
                    "latency_ms": time_ms() - t0,
                    "ts": _ts(),
                }
            )
        except Exception as e:
            crash_dump("PIPE_HANDLE", f"{e.__class__.__name__}: {e}\n{traceback.format_exc(limit=2)}")
            actions.append(
                {
                    "id": m.get("id", "?"),
                    "status": "error",
                    "error": str(e),
                    "ts": _ts(),
                    "latency_ms": time_ms() - t0,
                }
            )

    out = p.status / f"ACTIONS_{_ts()}.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for a in actions:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")

    dist = gate(actions)
    summ = {
        "ts": _ts(),
        "inbox_count": len(mails),
        "evaluated": len(actions),
        "distribution": dist,
        "pass_rule": "done=10,error=0,queued=0",
        "actions_jsonl": str(out),
    }
    (p.status / f"PIPE_SUMMARY_{_ts()}.json").write_text(
        json.dumps(summ, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"ok": (dist.get("error", 0) == 0), **summ}, ensure_ascii=False))


if __name__ == "__main__":
    main()
PY

###############################################################################
# 2) policy/engine.py — 匯入整理、typing 現代化、去除多語句
###############################################################################
cat > src/smart_mail_agent/policy/engine.py <<'PY'
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from smart_mail_agent.utils.config import paths


def _rules_path() -> Path:
    return paths().root / "policies" / "rules.yaml"


def load_rules() -> dict[str, Any]:
    p = _rules_path()
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def apply_policies(ctx: dict[str, Any]) -> dict[str, Any]:
    """
    ctx: {mail, intent, kie{fields}, intent_score}
    returns: {alerts:[], tickets:[], changes:[]}
    """
    rules = load_rules()
    out: dict[str, list] = {"alerts": [], "tickets": [], "changes": []}
    intent = ctx.get("intent")
    f = (ctx.get("kie") or {}).get("fields") or {}

    # 範例規則：高金額報價 -> 產生 alert
    if intent == "quote":
        try:
            thr = float((rules.get("quote") or {}).get("high_amount", 0))
        except Exception:
            thr = 0.0
        try:
            amt = float((f.get("amount") or "0").replace(",", ""))
            if amt >= thr:
                out["alerts"].append(
                    {
                        "level": (rules.get("quote") or {}).get("alert_level", "high"),
                        "message": f"High deal amount {amt} >= {thr}",
                    }
                )
        except Exception:
            pass

    # 範例：物流缺 tracking -> ticket
    if intent == "logistics" and not f.get("tracking_no"):
        out["tickets"].append({"type": "need_tracking"})

    # 範例：保固 -> 開 RMA
    if intent == "warranty":
        out["tickets"].append({"type": "rma_open"})

    return out
PY

###############################################################################
# 3) rag/compat.py — 保留相容載入，未使用標註 noqa
###############################################################################
cat > src/smart_mail_agent/rag/compat.py <<'PY'
from __future__ import annotations

try:
    from langchain.text_splitter import (  # type: ignore  # noqa: F401
        RecursiveCharacterTextSplitter,
    )
except Exception:
    from langchain.text_splitters import (  # type: ignore  # noqa: F401
        RecursiveCharacterTextSplitter,
    )

try:
    from langchain_community.vectorstores import FAISS  # type: ignore  # noqa: F401
except Exception:
    from langchain.vectorstores import FAISS  # type: ignore  # noqa: F401
PY

###############################################################################
# 4) rag/faiss_build.py — 匯入整齊、去除未用、拆單行多語句
###############################################################################
cat > src/smart_mail_agent/rag/faiss_build.py <<'PY'
from __future__ import annotations

import os
from pathlib import Path

from langchain.text_splitter import RecursiveCharacterTextSplitter  # type: ignore
from langchain_community.document_loaders import TextLoader
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

ROOT = Path(os.environ.get("SMA_ROOT") or Path(__file__).resolve().parents[3])
KB_DIR = Path(os.environ.get("KB_DIR") or (ROOT / "kb_docs"))
OUT = ROOT / "reports_auto" / "kb" / "faiss_index"


def build() -> dict[str, str | int]:
    if not KB_DIR.exists():
        return {"built": 0, "index": str(OUT)}

    texts = []
    for p in KB_DIR.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".txt", ".md"):
            texts.append(TextLoader(str(p), encoding="utf-8").load()[0])

    if not texts:
        return {"built": 0, "index": str(OUT)}

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    docs = []
    for d in texts:
        docs += splitter.split_documents([d])

    emb = OpenAIEmbeddings()
    vs = FAISS.from_documents(docs, emb)

    OUT.mkdir(parents=True, exist_ok=True)
    vs.save_local(str(OUT))
    return {"built": len(docs), "index": str(OUT)}
PY

###############################################################################
# 5) rag/provider.py — List -> list 等現代化 typing
###############################################################################
cat > src/smart_mail_agent/rag/provider.py <<'PY'
from __future__ import annotations

import hashlib
from typing import Any

try:
    from langchain_core.embeddings import Embeddings  # type: ignore
except Exception:

    class Embeddings:  # type: ignore
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            raise NotImplementedError

        def embed_query(self, text: str) -> list[float]:
            raise NotImplementedError


class HashEmb(Embeddings):
    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def _vec(self, t: str) -> list[float]:
        b = hashlib.sha1((t or "").encode("utf-8")).digest()
        return [b[i % len(b)] / 255.0 for i in range(self.dim)]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)
PY

###############################################################################
# 6) rpa/rag/provider.py — 拆開多語句
###############################################################################
if [ -f src/smart_mail_agent/rpa/rag/provider.py ]; then
  python - <<'PY'
from pathlib import Path
p=Path("src/smart_mail_agent/rpa/rag/provider.py")
s=p.read_text(encoding="utf-8")
s=s.replace("txt += f\"- {v}\\n\"; hits += 1", "txt += f\"- {v}\\n\"\n            hits += 1")
p.write_text(s, encoding="utf-8")
print("[patched] rpa/rag/provider.py")
PY
fi

###############################################################################
# 7) transport/mail.py — 乾淨化函式
###############################################################################
cat > src/smart_mail_agent/transport/mail.py <<'PY'
from __future__ import annotations

from email.message import EmailMessage
from typing import Tuple


def render_mime(
    to: str,
    subj: str,
    body: str,
    attachments: list[Tuple[str, bytes]] | None = None,
    sender: str | None = None,
) -> bytes:
    msg = EmailMessage()
    if sender:
        msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subj
    msg.set_content(body or "")
    for att in attachments or []:
        name, data = att
        msg.add_attachment(
            data,
            maintype="application",
            subtype="octet-stream",
            filename=name,
        )
    return msg.as_bytes()
PY

###############################################################################
# 8) transport/smtp_send.py — 分行、去除多語句
###############################################################################
cat > src/smart_mail_agent/transport/smtp_send.py <<'PY'
from __future__ import annotations

import email
import os
import smtplib
from datetime import datetime
from typing import Any, Dict

from smart_mail_agent.utils.config import paths


def _ts() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%S")


def send_smtp(mime_bytes: bytes, cfg: dict | None = None) -> Dict[str, Any]:
    p = paths()
    cfg = cfg or {}
    host = cfg.get("host") or os.getenv("SMTP_HOST")
    port = int(cfg.get("port") or os.getenv("SMTP_PORT") or 465)
    user = cfg.get("user") or os.getenv("SMTP_USER")
    pwd = cfg.get("pass") or os.getenv("SMTP_PASS")
    use_ssl = bool(cfg.get("ssl", True) if "ssl" in cfg else (os.getenv("SMTP_SSL", "1") == "1"))

    ts = _ts()
    out_eml = p.outbox / f"mail_{ts}.eml"
    out_eml.write_bytes(mime_bytes)

    if not (os.getenv("SEND_NOW") == "1"):
        return {"ok": True, "message_id": None, "eml": str(out_eml), "ts": ts, "sent": False}

    try:
        if use_ssl:
            s = smtplib.SMTP_SSL(host=host, port=port, timeout=20)
        else:
            s = smtplib.SMTP(host=host, port=port, timeout=20)
            s.starttls()
        if user and pwd:
            s.login(user, pwd)
        msg = email.message_from_bytes(mime_bytes)
        s.send_message(msg)
        s.quit()

        sent_dir = p.outbox / "sent"
        sent_dir.mkdir(exist_ok=True)
        out_eml.rename(sent_dir / out_eml.name)
        return {
            "ok": True,
            "message_id": msg.get("Message-Id"),
            "eml": str(sent_dir / out_eml.name),
            "ts": ts,
            "sent": True,
        }
    except Exception as e:
        retry_dir = p.outbox / "retry"
        retry_dir.mkdir(exist_ok=True)
        (retry_dir / out_eml.name).write_bytes(mime_bytes)
        return {"ok": False, "error": str(e), "eml": str(retry_dir / out_eml.name), "ts": ts, "sent": False}
PY

###############################################################################
# 9) utils/config.py — 拆匯入、保留介面 env_bool/paths()
###############################################################################
cat > src/smart_mail_agent/utils/config.py <<'PY'
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def env_bool(k: str, d: bool = False) -> bool:
    v = os.getenv(k)
    return d if v is None else str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass
class _Paths:
    root: Path
    outbox: Path
    status: Path


def _detect_root() -> Path:
    # 以環境變數優先；否則以專案為根；最後退回當前工作目錄
    env = os.getenv("SMA_ROOT")
    if env:
        return Path(env)
    git_root = os.popen("git rev-parse --show-toplevel 2>/dev/null").read().strip()
    return Path(git_root or os.getcwd())


def paths() -> _Paths:
    root = _detect_root()
    reports = root / "reports_auto"
    outbox = reports / "outbox"
    status = reports / "status"
    outbox.mkdir(parents=True, exist_ok=True)
    status.mkdir(parents=True, exist_ok=True)
    return _Paths(root=root, outbox=outbox, status=status)
PY

###############################################################################
# 10) run_action_handler.py — 匯入整齊 + 綁定閉包變數，消除 B023
###############################################################################
if [ -f src/smart_mail_agent/pipeline/run_action_handler.py ]; then
  cat > src/smart_mail_agent/pipeline/run_action_handler.py <<'PY'
from __future__ import annotations

import json
import time
import traceback
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Tuple

from smart_mail_agent.kie.infer import KIE
from smart_mail_agent.observability.audit_db import ensure_schema, insert_row, write_err_log
from smart_mail_agent.spam.ens import SpamEnsemble

from .action_handler import plan_actions


def _now() -> int:
    return int(time.time())


def _safe(fn: Callable[[], Any], tag: str, mail_id: str) -> Tuple[Any, str | None]:
    try:
        return fn(), None
    except Exception as e:
        write_err_log(tag, f"{mail_id}: {e.__class__.__name__}: {e}")
        return None, str(e)


def main(inbox_dir: str) -> None:
    ensure_schema()
    p = Path(inbox_dir)
    clf_spam = SpamEnsemble()
    clf_intent = None
    kie = KIE()
    cnt: Counter[str] = Counter()

    for fp in sorted(p.glob("*.txt")):
        mail_id = fp.stem
        text = fp.read_text(encoding="utf-8")

        y_spam = 0
        if clf_spam:
            y, err = _safe(lambda text=text: clf_spam.predict(text), "spam/predict", mail_id)
            y_spam = int(y == 1) if err is None else 0
        if y_spam == 1:
            cnt["spam"] += 1
            continue

        intent = "other"
        if clf_intent:
            lbl, err = _safe(lambda text=text: clf_intent.predict(text), "intent/predict", mail_id)
            intent = (lbl or "other") if err is None else "other"
        cnt[intent] += 1

        fields: dict[str, Any] = {}
        if kie:
            spans, _ = _safe(lambda text=text: kie.extract(text), "kie/extract", mail_id)
            if spans:
                fields["spans"] = spans

        plan_actions({"id": mail_id, "body": text}, {"intent": intent}, {"fields": fields})

    Path("reports_auto/status/INTENT_SUMMARY.json").write_text(
        json.dumps(cnt, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main("samples/inbox")
PY
fi

echo "[OK] files written. Running Ruff auto-fix..."
python - <<'PY'
import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "-q", "install", "--upgrade", "ruff"], check=True)
subprocess.run([sys.executable, "-m", "ruff", "check", "--fix", "src"], check=False)
print("[OK] ruff --fix done")
PY

echo "[NEXT]"
echo "1) . .venv_clean/bin/activate"
echo "2) ruff check src"
echo "3) pytest -q"
echo "4) python -m smart_mail_agent.pipeline.pipe_run --inbox samples"
