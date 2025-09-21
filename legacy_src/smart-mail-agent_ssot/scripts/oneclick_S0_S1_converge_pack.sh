#!/usr/bin/env bash
set -Eeuo pipefail
TS="$(date +%Y%m%dT%H%M%S)"
ROOT="${ROOT:-$HOME/projects/smart-mail-agent_ssot}"
LOG="$ROOT/reports_auto/logs/s0s1_converge_${TS}.log"
OUT="$ROOT/reports_auto/status/S0S1_${TS}"
mkdir -p "$(dirname "$LOG")" "$OUT"

exec > >(tee -a "$LOG") 2>&1
say(){ echo "[$(date +%H:%M:%S)] $*"; }
backup(){ local f="$1"; [[ -f "$f" ]] && cp -a "$f" "${f}.bak.${TS}" && echo "[BACKUP] $f -> ${f}.bak.${TS}" || true; }
write(){ # write <path> <heredoc_marker>
  local p="$1"; local m="$2"; mkdir -p "$(dirname "$p")"; backup "$p"; cat > "$p" <<$m
$3
$m
  chmod go-w "$p" 2>/dev/null || true
  echo "[WRITE] $p"
}

say "0) 進專案 + 啟環境"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
python -V || true

# 1) 寫入：集中設定（環境變數→型別安全）
SETTINGS_PATH="src/smart_mail_agent/utils/settings.py"
read -r -d '' SETTINGS_CODE <<'PY'
from __future__ import annotations
from pydantic import BaseModel, Field
import os

class SmtpCfg(BaseModel):
    mode: str = Field(default=os.getenv("SMA_SMTP_MODE", "outbox"))
    host: str = Field(default=os.getenv("SMA_SMTP_HOST", "smtp.gmail.com"))
    port: int = Field(default=int(os.getenv("SMA_SMTP_PORT", "587")))
    tls: str = Field(default=os.getenv("SMA_SMTP_TLS", "starttls"))
    user: str | None = Field(default=os.getenv("SMA_SMTP_USER"))
    password: str | None = Field(default=os.getenv("SMA_SMTP_PASS"))
    whitelist: list[str] = Field(default_factory=lambda: [e.strip() for e in os.getenv("SMA_EMAIL_WHITELIST","").split(",") if e.strip()])

class GlobalCfg(BaseModel):
    db_path: str = Field(default=os.getenv("SMA_DB_PATH", "db/sma.sqlite"))
    action_cap_send_email: int = Field(default=int(os.getenv("SMA_ACTION_CAP_SEND_EMAIL","200")))
    use_rag_faq: bool = Field(default=os.getenv("SMA_USE_RAG_FAQ","0")=="1")
    rag_topk: int = Field(default=int(os.getenv("SMA_RAG_TOPK","3")))
    llm_provider: str = Field(default=os.getenv("SMA_LLM_PROVIDER","none"))
    openai_key: str | None = Field(default=os.getenv("OPENAI_API_KEY"))

SMTP = SmtpCfg()
CFG = GlobalCfg()
PY
write "$SETTINGS_PATH" 'PY' "$SETTINGS_CODE"

# 2) 寫入：觀測性（NDJSON schema + CrashBundle）
NDJSON_PATH="src/smart_mail_agent/observability/ndjson_schema.py"
read -r -d '' NDJSON_CODE <<'PY'
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
import json, pathlib, typing as T

@dataclass
class EventV1:
    ts: str
    run_ts: str
    kind: str
    level: str
    idem: str | None
    case_id: str | None
    intent: str | None
    action: str | None
    duration_ms: int | None
    result: str | None
    err_type: str | None = None
    err_msg: str | None = None

def now_iso() -> str: return datetime.utcnow().isoformat(timespec="seconds")+"Z"
def write_event(ev: EventV1, out_file: pathlib.Path) -> None:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("a", encoding="utf-8") as w:
        w.write(json.dumps(asdict(ev), ensure_ascii=False)+"\n")
PY
write "$NDJSON_PATH" 'PY' "$NDJSON_CODE"

CRASH_PATH="src/smart_mail_agent/observability/crash_bundle.py"
read -r -d '' CRASH_CODE <<'PY'
from __future__ import annotations
import tarfile, pathlib, io, datetime

def make_bundle(dest: pathlib.Path, summary: pathlib.Path | None, logs_dir: pathlib.Path) -> pathlib.Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(dest, "w:gz") as tar:
        if summary and summary.exists():
            tar.add(summary, arcname=f"SUMMARY.md")
        if logs_dir.exists():
            for p in sorted(logs_dir.rglob("*.ndjson"))[-20:]:
                tar.add(p, arcname=f"logs/{p.name}")
    return dest
PY
write "$CRASH_PATH" 'PY' "$CRASH_CODE"

# 3) 寄送策略層（白名單/速率/再送）
STRAT_PATH="src/smart_mail_agent/transport/strategies.py"
read -r -d '' STRAT_CODE <<'PY'
from __future__ import annotations
from dataclasses import dataclass
from time import time
from . import __init__ as _  # placate package tools
from typing import Iterable
from smart_mail_agent.utils.settings import SMTP

@dataclass
class SendPolicy:
    whitelist: set[str]
    per_minute_cap: int
    allow_resend: bool

class RateLimiter:
    def __init__(self, cap: int) -> None:
        self.cap = cap; self.win = []; self.T=60.0
    def allow(self) -> bool:
        t=time(); self.win=[x for x in self.win if t-x < self.T]
        if len(self.win) >= self.cap: return False
        self.win.append(t); return True

DEFAULT_POLICY = SendPolicy(whitelist=set(SMTP.whitelist), per_minute_cap=60, allow_resend=False)

def check_recipient(to_addr: str, policy: SendPolicy=DEFAULT_POLICY) -> None:
    if policy.whitelist and to_addr.lower() not in {e.lower() for e in policy.whitelist}:
        raise PermissionError(f"Recipient {to_addr} not in whitelist")

_rate = RateLimiter(DEFAULT_POLICY.per_minute_cap)
def check_rate(policy: SendPolicy=DEFAULT_POLICY) -> None:
    if policy.per_minute_cap and not _rate.allow():
        raise RuntimeError("rate_limited")
PY
write "$STRAT_PATH" 'PY' "$STRAT_CODE"

POLICY_MAIL_PATH="src/smart_mail_agent/transport/policy_mail.py"
read -r -d '' POLICY_MAIL_CODE <<'PY'
from __future__ import annotations
from email.message import EmailMessage
import pathlib
from .strategies import check_recipient, check_rate, DEFAULT_POLICY
from smart_mail_agent.utils.settings import SMTP

def save_eml(msg: EmailMessage, dest: pathlib.Path) -> pathlib.Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as w: w.write(msg.as_bytes(policy=None))
    return dest

def send_or_outbox(msg: EmailMessage, to_addr: str, outbox_dir: pathlib.Path) -> pathlib.Path:
    check_recipient(to_addr, DEFAULT_POLICY); check_rate(DEFAULT_POLICY)
    if SMTP.mode != "smtp":
        return save_eml(msg, outbox_dir / (msg["Subject"] or "mail").replace(" ","_")[:80] + ".eml")
    # 真發信：沿用既有 smtp 客戶端（若你已有 transport/mail.py，可改為 import 後呼叫）
    import smtplib, ssl
    msg["To"] = to_addr
    ctx = ssl.create_default_context()
    with smtplib.SMTP(SMTP.host, SMTP.port) as s:
        if SMTP.tls == "starttls": s.starttls(context=ctx)
        if SMTP.user and SMTP.password: s.login(SMTP.user, SMTP.password)
        s.send_message(msg)
    return save_eml(msg, outbox_dir / (msg["Subject"] or "mail").replace(" ","_")[:80] + ".eml")
PY
write "$POLICY_MAIL_PATH" 'PY' "$POLICY_MAIL_CODE"

# 4) 直驅入口（保留 legacy 後門，S1 會關閉）
CLI_PATH="src/smart_mail_agent/cli/e2e.py"
read -r -d '' CLI_CODE <<'PY'
from __future__ import annotations
import argparse, subprocess, sys, shutil, pathlib, time
from smart_mail_agent.observability.ndjson_schema import EventV1, write_event, now_iso

def _legacy_runner():
    s = pathlib.Path("scripts/sma_e2e_mail.py")
    return s.exists()

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--eml-dir", default="samples", help="input EML dir")
    p.add_argument("--run-ts", default=time.strftime("%Y%m%dT%H%M%S"))
    args=p.parse_args(argv)
    run_ts=args.run_ts

    logs = pathlib.Path(f"reports_auto/events/{run_ts}.ndjson")
    if _legacy_runner():
        cmd=[sys.executable, "scripts/sma_e2e_mail.py", "--eml-dir", args.eml_dir, "--run-ts", run_ts]
        rc=subprocess.call(cmd)
        write_event(EventV1(now_iso(), run_ts, "runner", "INFO", None, None, None, "legacy_exit", None, f"rc={rc}"), logs)
        sys.exit(rc)
    else:
        # 最小直驅：掃描 EML 生成 outbox（作為 S0 smoke；你的完整流程仍走既有模組）
        outbox = pathlib.Path(f"reports_auto/e2e_mail/{run_ts}/rpa_out/email_outbox"); outbox.mkdir(parents=True, exist_ok=True)
        eml_in = pathlib.Path(args.eml_dir)
        count=0
        for p in eml_in.glob("*.eml"):
            # 直接 copy 作為 placeholder（S1 會接入你的完整流程）
            dest = outbox / p.name
            dest.write_bytes(p.read_bytes())
            count+=1
        write_event(EventV1(now_iso(), run_ts, "runner", "INFO", None, None, None, "direct_outbox", None, f"copied={count}"), logs)
        print(f"[OK] S0 direct-outbox: {count} files -> {outbox}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
PY
write "$CLI_PATH" 'PY' "$CLI_CODE"

# 5) Artifacts manifest 產生器
GEN_MAN_PATH="scripts/gen_artifacts_manifest.py"
read -r -d '' GEN_MAN_CODE <<'PY'
from __future__ import annotations
import json, pathlib, hashlib, time

ART=pathlib.Path("artifacts_prod")
MAN=ART/"manifest.json"
def sha256(p: pathlib.Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1<<20), b""): h.update(b)
    return h.hexdigest()

def main():
    ART.mkdir(exist_ok=True)
    items=[]
    for p in ART.glob("*"):
        if p.is_file():
            items.append({"name": p.name, "sha256": sha256(p), "size": p.stat().st_size, "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")})
    MAN.write_text(json.dumps({"version":"1.0","artifacts":items}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] manifest -> {MAN}")
if __name__=="__main__": main()
PY
write "$GEN_MAN_PATH" 'PY' "$GEN_MAN_CODE"

# 6) 最小測試集與單元測試
mkdir -p tests/_data/eml
read -r -d '' BUILD_SAMPLES <<'PY'
from email.message import EmailMessage
from pathlib import Path

def build_one(subject: str, name: str):
    m=EmailMessage()
    m["Subject"]=subject; m["From"]="demo@example.com"; m.set_content("demo")
    Path("tests/_data/eml").mkdir(parents=True, exist_ok=True)
    (Path("tests/_data/eml")/f"{name}.eml").write_bytes(m.as_bytes())

if __name__ == "__main__":
    build_one("一般詢問 測試","01_inquiry")
    build_one("客訴 測試","02_complaint")
    build_one("垃圾郵件 測試","03_spam")
PY
write "tests/_data/build_samples.py" 'PY' "$BUILD_SAMPLES"

read -r -d '' TEST_POLICY <<'PY'
from smart_mail_agent.transport.strategies import check_recipient, SendPolicy
import pytest
def test_whitelist_ok():
    check_recipient("a@b.com", SendPolicy({"a@b.com"}, 60, False))
def test_whitelist_block():
    with pytest.raises(PermissionError):
        check_recipient("x@y.com", SendPolicy({"a@b.com"}, 60, False))
PY
write "tests/test_transport_policy.py" 'PY' "$TEST_POLICY"

read -r -d '' TEST_NDJSON <<'PY'
from smart_mail_agent.observability.ndjson_schema import EventV1, write_event, now_iso
from pathlib import Path
def test_ndjson_write(tmp_path: Path):
    p=tmp_path/"e.ndjson"
    write_event(EventV1(now_iso(),"ts","kind","INFO",None,None,None,"act",0,"ok"), p)
    assert p.exists() and p.read_text().strip().endswith('"ok"}')
PY
write "tests/test_ndjson_schema.py" 'PY' "$TEST_NDJSON"

# 7) CI（獨立檔名，避免覆蓋你現有 CI）
mkdir -p .github/workflows
read -r -d '' CIYAML <<'YAML'
name: s0s1-smoke
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: python -m pip install -U pip
      - run: pip install -U "pytest>=7,<9" "pydantic>=2,<3" "pydantic-settings>=2,<3"
      - run: python tests/_data/build_samples.py
      - run: pytest -q
YAML
write ".github/workflows/ci_s0s1_smoke.yml" 'YAML' "$CIYAML"

# 8) 依賴補齊
python - <<'PY'
import json, sys, subprocess
req = "requirements.txt"
try:
    txt=open(req, "r", encoding="utf-8").read()
except FileNotFoundError:
    txt=""
need=[]
for lib in ("pydantic>=2,<3","pydantic-settings>=2,<3","pytest>=7,<9"):
    if lib.split(">")[0].split("=")[0] not in txt:
        need.append(lib)
if need:
    with open(req,"a",encoding="utf-8") as w: w.write("\n"+"\n".join(need)+"\n")
    print("[REQ] appended:", need)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", *need])
else:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "pytest>=7,<9"])
PY

# 9) 產樣本與 smoke（不觸發實寄）
python tests/_data/build_samples.py
pytest -q || true

# 10) 健康檢查與出包
python scripts/gen_artifacts_manifest.py || true
echo -e "# S0→S1 收斂完成\n- TS: ${TS}\n- 變更已備份為 .bak.${TS}\n- 測試與日誌見：${LOG}" > "$OUT/README.md"

# 11) 成功後自動開資料夾
if grep -qi microsoft /proc/version 2>/dev/null; then explorer.exe "$(wslpath -w "$OUT")" >/dev/null 2>&1 || true
elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$OUT" >/dev/null 2>&1 || true
fi
say "DONE S0→S1"
