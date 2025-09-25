#!/usr/bin/env bash
# 同步 artifacts_inbox -> 專案標準位置；兼容資料夾與 zip；失敗自動打包錯誤
set -Eeuo pipefail
set -o pipefail

ROOT="/home/youjie/projects/smart-mail-agent_ssot"
INBOX="$ROOT/artifacts_inbox"
TS="$(date +%Y%m%dT%H%M%S)"
RUN_LOG="reports_auto/logs/INBOX_IMPORT_${TS}.log"
ERR_LOG="reports_auto/logs/INBOX_IMPORT_ERROR_${TS}.log"
CRASH_DIR="reports_auto/errors/INBOX_IMPORT_CRASH_${TS}"

log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$RUN_LOG"; }
die(){ echo "[FATAL] $*" | tee -a "$RUN_LOG" "$ERR_LOG"; exit 1; }

mkdir -p reports_auto/logs reports_auto/status reports_auto/eval db scripts artifacts_prod artifacts kie data

unpack () {
  # $1: zip path, $2: dest dir
  local z="$1"; local dst="$2"
  if command -v unzip >/dev/null 2>&1; then
    unzip -oq "$z" -d "$dst"
  elif command -v bsdtar >/dev/null 2>&1; then
    bsdtar -xf "$z" -C "$dst"
  else
    die "無 unzip/bsdtar，無法解壓：$z"
  fi
}

trap 'ec=$?; if [[ $ec -ne 0 ]]; then mkdir -p "$CRASH_DIR"; [[ -s "$RUN_LOG" ]] && cp -f "$RUN_LOG" "$CRASH_DIR/"; [[ -s "$ERR_LOG" ]] && cp -f "$ERR_LOG" "$CRASH_DIR/"; [[ -f reports_auto/logs/pipeline.ndjson ]] && tail -n 200 reports_auto/logs/pipeline.ndjson > "$CRASH_DIR/pipeline_tail.last200.ndjson" || true; echo "[CRASH] 詳情：$CRASH_DIR"; fi; exit $ec' EXIT

log "開始同步 artifacts_inbox：$INBOX"

# 1) Spam
if [[ -d "$INBOX/spam" ]]; then
  log "複製 spam 目錄 -> artifacts_prod/"
  cp -af "$INBOX/spam/." artifacts_prod/
elif [[ -f "$INBOX/spam.zip" ]]; then
  log "解壓 spam.zip -> tmp 並複製"
  TMP="reports_auto/tmp/spam_${TS}"; mkdir -p "$TMP"; unpack "$INBOX/spam.zip" "$TMP"
  cp -af "$TMP/." "$ROOT/"
elif [[ -f "$INBOX/model_pipeline.pkl" ]] || [[ -f "$INBOX/ens_thresholds.json" ]]; then
  log "複製 spam 散檔 -> artifacts_prod/"
  [[ -f "$INBOX/model_pipeline.pkl" ]]    && cp -f "$INBOX/model_pipeline.pkl" artifacts_prod/
  [[ -f "$INBOX/ens_thresholds.json" ]]   && cp -f "$INBOX/ens_thresholds.json" artifacts_prod/
else
  log "[WARN] 找不到 spam 產物，若專案既有可略過"
fi

# 2) Intent
if [[ -d "$INBOX/intent" ]]; then
  log "複製 intent 目錄 -> artifacts/ 與 reports_auto/"
  [[ -f "$INBOX/intent/intent_pro_cal.pkl" ]] && cp -f "$INBOX/intent/intent_pro_cal.pkl" artifacts/
  [[ -f "$INBOX/intent/intent_thresholds.json" ]] && cp -f "$INBOX/intent/intent_thresholds.json" reports_auto/
elif [[ -f "$INBOX/intent.zip" ]]; then
  log "解壓 intent.zip -> tmp 並複製"
  TMP="reports_auto/tmp/intent_${TS}"; mkdir -p "$TMP"; unpack "$INBOX/intent.zip" "$TMP"
  [[ -f "$TMP/artifacts/intent_pro_cal.pkl" ]] && cp -f "$TMP/artifacts/intent_pro_cal.pkl" artifacts/
  [[ -f "$TMP/reports_auto/intent_thresholds.json" ]] && cp -f "$TMP/reports_auto/intent_thresholds.json" reports_auto/
  [[ -f "$TMP/intent_pro_cal.pkl" ]] && cp -f "$TMP/intent_pro_cal.pkl" artifacts/
  [[ -f "$TMP/intent_thresholds.json" ]] && cp -f "$TMP/intent_thresholds.json" reports_auto/
else
  [[ -f "$INBOX/intent_pro_cal.pkl" ]] && cp -f "$INBOX/intent_pro_cal.pkl" artifacts/ || true
  [[ -f "$INBOX/intent_thresholds.json" ]] && cp -f "$INBOX/intent_thresholds.json" reports_auto/ || true
fi

# 若門檻不存在，建立預設
if [[ ! -f reports_auto/intent_thresholds.json ]]; then
  log "建立預設 intent 門檻檔 reports_auto/intent_thresholds.json"
  cat > reports_auto/intent_thresholds.json <<'JSON'
{"報價":0.50,"技術支援":0.50,"投訴":0.50,"規則詢問":0.50,"資料異動":0.50,"其他":0.40}
JSON
fi

# 3) KIE
# 優先處理 artifacts_inbox/kie/kie/ 的權重結構（你目前的情況）
if [[ -d "$INBOX/kie/kie" ]]; then
  log "同步 kie/kie -> 專案 kie/"
  rm -rf kie && mkdir -p kie
  cp -af "$INBOX/kie/kie/." kie/
elif [[ -d "$INBOX/kie_min_bundle" ]]; then
  log "同步 kie_min_bundle -> 專案 kie/"
  rm -rf kie && mkdir -p kie
  cp -af "$INBOX/kie_min_bundle/." kie/
elif compgen -G "$INBOX/kie_min_bundle_*.zip" >/dev/null; then
  Z=$(ls -1 "$INBOX"/kie_min_bundle_*.zip | head -n1)
  log "解壓 $Z -> 專案 kie/"
  rm -rf kie && mkdir -p kie
  TMP="reports_auto/tmp/kie_${TS}"; mkdir -p "$TMP"; unpack "$Z" "$TMP"
  # 適配多層資料夾
  if [[ -d "$TMP/kie" ]]; then cp -af "$TMP/kie/." kie/
  else cp -af "$TMP/." kie/; fi
elif [[ -f "$INBOX/kie.zip" ]]; then
  log "解壓 kie.zip -> 專案 kie/"
  rm -rf kie && mkdir -p kie
  TMP="reports_auto/tmp/kie_${TS}"; mkdir -p "$TMP"; unpack "$INBOX/kie.zip" "$TMP"
  if [[ -d "$TMP/kie" ]]; then cp -af "$TMP/kie/." kie/
  else cp -af "$TMP/." kie/; fi
elif [[ -d "$INBOX/kie" ]]; then
  log "同步 artifacts_inbox/kie -> 專案 kie/"
  rm -rf kie && mkdir -p kie
  cp -af "$INBOX/kie/." kie/
else
  log "[WARN] 找不到 kie 產物；之後將回退規則抽取"
fi

# 若 model.safetensors 不在專案 kie/，嘗試連結 inbox 的
if [[ ! -f "kie/model.safetensors" ]] && [[ -f "$INBOX/kie/kie/model.safetensors" ]]; then
  log "建立外部權重軟連結 -> kie/model.safetensors"
  ln -sf "$INBOX/kie/kie/model.safetensors" "kie/model.safetensors"
fi

# 4) 匯入 4 資料到 data/ 供評估
if [[ -d "$INBOX/4" ]] || [[ -f "$INBOX/4.zip" ]]; then
  log "開始匯入 4 資料集 -> data/"
  TMP4="reports_auto/tmp/inbox4_${TS}"; mkdir -p "$TMP4"
  if [[ -f "$INBOX/4.zip" ]]; then unpack "$INBOX/4.zip" "$TMP4"; else cp -af "$INBOX/4" "$TMP4/"; fi
  if [[ ! -f scripts/sma_ingest_4_snapshot.py ]]; then
    cat > scripts/sma_ingest_4_snapshot.py <<'PY'
import argparse, json
from pathlib import Path
MAP_INTENT_EN2ZH={"biz_quote":"報價","tech_support":"技術支援","complaint":"投訴","policy_qa":"規則詢問","profile_update":"資料異動","other":"其他"}
def write_jsonl(p, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p,"w",encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False)+"\n")
def ingest_spam(src, dst):
    sp = src/"4"/"all.jsonl"
    if not sp.exists(): return 0
    rows=[]
    for ln in sp.read_text("utf-8").splitlines():
        if not ln.strip(): continue
        o=json.loads(ln)
        txt=o.get("text") or ((o.get("subject","")+"\n"+o.get("body","")).strip())
        rows.append({"text":txt, "spam": 1 if o.get("label")=="spam" else 0})
    out=dst/"spam_eval"/"dataset.jsonl"; write_jsonl(out, rows); return len(rows)
def ingest_intent(src, dst):
    rows=[]; cands=["i_demo.jsonl","demo_intent.jsonl","i_20250901_full.jsonl"]
    for name in cands:
        p=src/"4"/name
        if p.exists():
            for ln in p.read_text("utf-8").splitlines():
                if not ln.strip(): continue
                o=json.loads(ln)
                txt=o.get("text") or ((o.get("subject","")+"\n"+o.get("body","")).strip())
                lab=o.get("label"); lab=MAP_INTENT_EN2ZH.get(lab,lab)
                rows.append({"text":txt,"intent":lab})
    if rows:
        out=dst/"intent_eval"/"dataset.jsonl"; write_jsonl(out, rows); return len(rows)
    return 0
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--src",required=True); ap.add_argument("--dst",default="data")
    a=ap.parse_args(); src=Path(a.src); dst=Path(a.dst)
    ns=ingest_spam(src,dst); ni=ingest_intent(src,dst)
    print(f"[OK] ingest spam={ns} intent={ni}")
if __name__=="__main__": main()
PY
  fi
  python scripts/sma_ingest_4_snapshot.py --src "$TMP4" --dst data | tee -a "$RUN_LOG" || true
else
  log "[INFO] 未提供 4 資料，略過資料匯入"
fi

# 5) 產生 KIE 推論介面（若不存在）
if [[ ! -f "kie/infer.py" ]]; then
  log "生成 kie/infer.py"
  cat > kie/infer.py <<'PY'
import os, re
from pathlib import Path
try:
    from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
    _TRANS = True
except Exception:
    _TRANS = False

ROOT = Path(os.getenv("SMA_ROOT", "/home/youjie/projects/smart-mail-agent_ssot"))
KIE_DIR = ROOT/"kie"
_LABEL_MAP = {
    "B-date_time":"date_time","I-date_time":"date_time",
    "B-amount":"amount","I-amount":"amount",
    "B-env":"env","I-env":"env",
    "B-sla":"sla","I-sla":"sla",
}

_nlp = None
def _load():
    global _nlp
    if os.getenv("KIE_DISABLE","0")=="1" or not _TRANS:
        _nlp = None; return
    tok = AutoTokenizer.from_pretrained(str(KIE_DIR), local_files_only=True)
    mdl = AutoModelForTokenClassification.from_pretrained(str(KIE_DIR), local_files_only=True)
    _nlp = pipeline("token-classification", model=mdl, tokenizer=tok, aggregation_strategy="simple")

def _regex_fallback(text):
    spans=[]
    m = re.search(r"(20\\d{2}[-/\\.](0?[1-9]|1[0-2])[-/\\.](0?[1-9]|[12]\\d|3[01]))", text)
    if m: spans.append(("date_time", m.group(1), m.start(), m.end()))
    m = re.search(r"(NTD|NT\\$|\\$)\\s?([0-9]{1,3}(,[0-9]{3})*(\\.[0-9]+)?|[0-9]+(\\.[0-9]+)?)", text)
    if m: spans.append(("amount", m.group(0), m.start(), m.end()))
    for env in ["prod","staging","dev","UAT","uat"]:
        i=text.lower().find(env.lower())
        if i>=0: spans.append(("env", env, i, i+len(env)))
    m = re.search(r"(\\d+)\\s*(hours|hrs|days|天|小時)", text, re.I)
    if m: spans.append(("sla", m.group(0), m.start(), m.end()))
    return spans

def extract(text: str):
    if _nlp is None:
        try: _load()
        except Exception: _nlp=None
    if _nlp is None: return _regex_fallback(text)
    outs = _nlp(text)
    spans=[]
    for o in outs:
        lab = _LABEL_MAP.get(o["entity_group"], o["entity_group"])
        if lab in {"date_time","amount","env","sla"}:
            start, end = int(o["start"]), int(o["end"])
            spans.append((lab, text[start:end], start, end))
    return spans
PY
fi

# 6) 產生資產驗證腳本（若不存在）
if [[ ! -f scripts/sma_validate_assets.py ]]; then
cat > scripts/sma_validate_assets.py <<'PY'
#!/usr/bin/env python3
import os, json, importlib.util, sys
from pathlib import Path
ROOT = Path("/home/youjie/projects/smart-mail-agent_ssot")
ok=True
def need(p, name):
    global ok
    print(("[OK] " if p.exists() else "[MISS] ")+f"{name}: {p}")
    if not p.exists(): ok=False
need(ROOT/"artifacts_prod"/"model_pipeline.pkl","Spam model")
need(ROOT/"artifacts_prod"/"ens_thresholds.json","Spam thresholds")
need(ROOT/"artifacts"/"intent_pro_cal.pkl","Intent model")
need(ROOT/"reports_auto"/"intent_thresholds.json","Intent thresholds")
need(ROOT/"kie"/"config.json","KIE config")
need(ROOT/"kie"/"tokenizer_config.json","KIE tokenizer_config.json")
need(ROOT/"kie"/"sentencepiece.bpe.model","KIE sentencepiece.bpe.model")
print(("[OK] KIE model.safetensors: present" if (ROOT/"kie"/"model.safetensors").exists() else "[WARN] KIE model.safetensors: missing"))
if (ROOT/"kie"/"infer.py").exists():
    try:
        spec=importlib.util.spec_from_file_location("kie_infer", ROOT/"kie"/"infer.py")
        m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        assert hasattr(m,"extract")
        print("[OK] KIE infer.py: extract 存在")
    except Exception as e:
        print("[ERR] KIE infer.py 無法載入：", e); ok=False
print("[RESULT]", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
PY
fi

log "匯入完成"
