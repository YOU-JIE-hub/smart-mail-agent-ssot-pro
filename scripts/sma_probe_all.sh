#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace

# ---------- Run 目錄（嚴格時間戳；禁止 ${RUN_DIR} 字面） ----------
TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/probe/${TS}"
LOG="${OUT}/run.log"
ERR="${OUT}/probe.err"
mkdir -p "${OUT}"

# ---------- 輸出鏡射到 run.log ----------
exec > >(tee -a "${LOG}") 2>&1

# ---------- 自動載入 env.default（若存在） ----------
[ -f scripts/env.default ] && export $(grep -v '^\s*#' scripts/env.default | xargs) || true

# ---------- 跨平台開資料夾 ----------
open_dir() {
  local p="$1"
  if command -v explorer.exe >/dev/null 2>&1; then
    explorer.exe "$(wslpath -w "$p")" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$p" >/dev/null 2>&1 || true
  fi
}

# ---------- 統一 ERR trap：只產生單一 .err + tail + 自動開資料夾 ----------
on_err() {
  local ec=$?
  {
    echo "TIME: $(date -Is)"
    echo "EXIT_CODE: ${ec}"
    echo "BASH_COMMAND: ${BASH_COMMAND:-<none>}"
  } >"${ERR}" || true
  echo ""
  echo "[FAIL] error file: ${ERR}"
  echo "--------------------------------------------------"
  tail -n 200 "${ERR}" 2>/dev/null || true
  echo "--------------------------------------------------"
  open_dir "${OUT}"
  exit "${ec}"
}
trap on_err ERR

# ---------- EXIT：成功也開資料夾（你偏好完成後可直接檢視） ----------
trap 'echo "[*] REPORT DIR: ${OUT}"; open_dir "${OUT}"' EXIT

# ---------- 最小 ZeroPad（只為反序列化；不改寬度；不動核心碼） ----------
mkdir -p vendor/sma_tools
cat > vendor/sma_tools/__init__.py <<'PY'
__all__ = ["sk_zero_pad"]
PY
cat > vendor/sma_tools/sk_zero_pad.py <<'PY'
from __future__ import annotations
import numpy as np
try:
    from scipy import sparse as sp
except Exception:  # 無 SciPy 時提供極簡替身，避免崩潰（維度僅作占位）
    class _CSR:
        def __init__(self, shape): self._shape = shape
        @property
        def shape(self): return self._shape
    class sp:  # type: ignore
        @staticmethod
        def csr_matrix(x, dtype=None): 
            try:
                r = len(x); c = len(x[0]) if r and hasattr(x[0],'__len__') else (x.shape[1] if hasattr(x,'shape') else 1)
            except Exception: 
                r, c = 1, 1
            return _CSR((r,c))
from sklearn.base import BaseEstimator, TransformerMixin
class ZeroPad(BaseEstimator, TransformerMixin):
    def __init__(self, width:int=1, dtype=np.float64, **kwargs):
        try: self.width = int(width) if width else 1
        except Exception: self.width = 1
        self.dtype = dtype
        self._extra = dict(kwargs)
    def __setstate__(self, state):
        self.__dict__.update(state or {})
        if not hasattr(self,"width"): self.width = 1
        if not hasattr(self,"dtype"): self.dtype = np.float64
    def fit(self, X, y=None): return self
    def transform(self, X): return sp.csr_matrix((len(X), self.width))
PY

# ---------- Python 盤點主程式（嚴禁「from pathlib import Path, json」） ----------
python - <<'PY' "${OUT}"
import os, sys, json, re, glob, traceback, importlib.util, sqlite3, faulthandler
from pathlib import Path
from datetime import datetime

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
pylog = open(OUT/"py_run.log","w",encoding="utf-8")
faulthandler.enable(pylog)

def log(*a): 
    print(*a)
    print(*a, file=pylog, flush=True)

# ===== 0) 環境快照 =====
env = {
  "cwd": os.getcwd(),
  "python": sys.version.split()[0],
  "PYTHONPATH": os.environ.get("PYTHONPATH",""),
  "SMA_EML_DIR": os.environ.get("SMA_EML_DIR",""),
}
# 可選：版本查詢（失敗不終止）
for m in ("numpy","scipy","sklearn","joblib"):
    try: env[m] = __import__(m).__version__
    except Exception: env[m] = "NA"
(OUT/"env_snapshot.json").write_text(json.dumps(env,ensure_ascii=False,indent=2),encoding="utf-8")

missing, alerts = [], []
findings = {"intent":{}, "spam":{}, "kie":{}, "configs":{}, "db":{}, "gates":{}}

# ===== 1) 守門掃描（禁 tri_*/safe_*/adapters、禁 tickets.md、禁 ${RUN_DIR}、禁 bad import）=====
EXCL_DIRS = re.compile(r"/(\.venv|venv|reports_auto|artifacts_inbox|dist|build|node_modules|\.git)(/|$)")
BAD_IMPORT = re.compile(r"\bfrom\s+pathlib\s+import\s+Path\s*,\s*json\b")
TRI_ENTRY  = re.compile(r"(^|/)(tri_|tri-)[^/\n]+\.(py|sh)\b")
SAFE_ENTRY = re.compile(r"(^|/)(safe_|safe-)[^/\n]+\.(py|sh)\b")
ADAPTERS_D = re.compile(r"(^|/)adapters(/|$)")
TRISTACK_D = re.compile(r"(^|/)tri_stack(/|$)")
LITERAL_RD = re.compile(r"\$\{?RUN_DIR\}?")
TICKETS_MD = re.compile(r"(^|/)tickets\.md\b")
SET_EE     = re.compile(r"\bset\s+-E[e]uo?\s+pipefail\b|(?:^|\s)-o\s+errtrace\b")
FAULTH     = re.compile(r"\bfaulthandler\b")
SMA_EML    = re.compile(r"\bSMA_EML_DIR\b")

gate_hits = {k: [] for k in ["bad_import","tri_entry","safe_entry","adapters_dir","tri_stack_dir","literal_RUN_DIR","tickets_md","set_eepipefail","faulthandler","SMA_EML_DIR"]}

def scan_file(p: Path):
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return
    if BAD_IMPORT.search(text): gate_hits["bad_import"].append(str(p))
    if TRI_ENTRY.search(p.as_posix()) or TRI_ENTRY.search(text): gate_hits["tri_entry"].append(str(p))
    if SAFE_ENTRY.search(p.as_posix()) or SAFE_ENTRY.search(text): gate_hits["safe_entry"].append(str(p))
    if ADAPTERS_D.search(p.as_posix()): gate_hits["adapters_dir"].append(str(p))
    if TRISTACK_D.search(p.as_posix()): gate_hits["tri_stack_dir"].append(str(p))
    if LITERAL_RD.search(text): gate_hits["literal_RUN_DIR"].append(str(p))
    if TICKETS_MD.search(p.as_posix()): gate_hits["tickets_md"].append(str(p))
    if not SET_EE.search(text) and p.suffix in (".sh",""): gate_hits["set_eepipefail"].append(str(p))
    if not FAULTH.search(text) and p.suffix==".py": gate_hits["faulthandler"].append(str(p))
    if SMA_EML.search(text): gate_hits["SMA_EML_DIR"].append(str(p))

ROOT = Path(".").resolve()
for dp, dn, fn in os.walk(ROOT):
    dpp = Path(dp)
    if EXCL_DIRS.search(dpp.as_posix() + "/"): 
        continue
    for name in fn:
        p = dpp / name
        if p.suffix.lower() in (".py",".sh",".md",".yml",".yaml",".ini",".cfg",".toml",".txt",".json",".sql",".csv",".tsv",".html",".xml",".ps1","") and p.is_file():
            scan_file(p)

(OUT/"gate_scan.json").write_text(json.dumps(gate_hits,ensure_ascii=False,indent=2),encoding="utf-8")
findings["gates"] = {k: len(v) for k,v in gate_hits.items()}

# ===== 2) 綁訓練 rules 模組（正確 __file__；載入失敗不終止）=====
def load_module_from_file(mod_name: str, file_path: str):
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"spec load failed for {mod_name} at {file_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)  # 提供 __file__/__package__
    return mod

rules_src = None
try:
    cands = sorted(glob.glob("intent/**/.sma_tools/runtime_threshold_router.py", recursive=True))
    if cands:
        rules_src = str(Path(cands[-1]).resolve())
        mod = load_module_from_file("vendor.rules_features", rules_src)
        # 註冊歷史別名（供 pickle 參照）
        for alias in ("train_pro","train_pro_fresh","sma_tools.runtime_threshold_router","runtime_threshold_router"):
            sys.modules[alias] = mod
        import __main__ as M
        M.rules_feat = getattr(mod, "rules_feat", None)
    else:
        alerts.append("intent.rules: 未找到 .sma_tools/runtime_threshold_router.py")
        missing.append({"need":"runtime_threshold_router.py","where":"intent/**/.sma_tools/","why":"與訓練期特徵完全對齊"})
except Exception as e:
    alerts.append(f"intent.rules: 載入失敗: {type(e).__name__}: {e}")
findings["intent"]["rules_module"] = rules_src or "NOT_FOUND"

# ===== 3) Intent 模型探測（不 pad；只診斷）=====
try:
    import joblib, numpy as np
    try:
        from scipy import sparse as sp
    except Exception:
        class _CSR: 
            def __init__(self, shape): self._shape = shape
            @property
            def shape(self): return self._shape
        class sp:  # type: ignore
            @staticmethod
            def csr_matrix(x): 
                try:
                    r = len(x); c = len(x[0]) if r and hasattr(x[0],'__len__') else 1
                except Exception: r, c = 1, 1
                return _CSR((r,c))

    def unwrap(obj):
        if hasattr(obj,"predict"): return obj
        if isinstance(obj, dict):
            for k in ("pipe","pipeline","estimator","clf","model"):
                if k in obj and hasattr(obj[k],"predict"): return obj[k]
        return obj

    def probe_pkl(pkl: str):
        info = {"path":pkl,"load_ok":False,"n_features_in":None,"branch_dims":{}, "sum_branch":None, "steps":[],"msg":""}
        try:
            obj = joblib.load(pkl)
            est = unwrap(obj)
            info["steps"] = [(n, type(s).__name__) for n,s in getattr(est,"steps",[])]
            clf = est.steps[-1][1] if hasattr(est,"steps") else est
            nfi = getattr(clf,"n_features_in_", None)
            if nfi is None and hasattr(clf,"base_estimator"):
                nfi = getattr(clf.base_estimator,"n_features_in_", None)
            info["n_features_in"] = int(nfi) if nfi is not None else None
            feats = None
            if hasattr(est,"steps"):
                d = dict(est.steps); feats = d.get("features") or d.get("pre") or d.get("union")
            if feats and hasattr(feats,"transformer_list"):
                xs = ["報價與交期","技術支援","發票抬頭","退訂連結"]
                dims={}
                for name,sub in feats.transformer_list:
                    try:
                        X = sub.transform(xs)
                        if hasattr(sp,"issparse") and getattr(sp,"issparse",None):
                            X = X.tocsr() if sp.issparse(X) else sp.csr_matrix(X)
                        else:
                            X = sp.csr_matrix(X)
                        dims[name] = int(X.shape[1])
                    except Exception as e:
                        dims[name] = f"ERR:{type(e).__name__}"
                info["branch_dims"] = dims
                s = sum(v for v in dims.values() if isinstance(v,int))
                info["sum_branch"] = s
            info["load_ok"] = True
        except Exception as e:
            info["msg"] = f"{type(e).__name__}: {e}"
        return info

    intent_pkls = sorted(set(
        glob.glob("artifacts/intent_*.pkl") +
        glob.glob("intent/**/artifacts/intent_pro_cal.pkl", recursive=True) +
        glob.glob("artifacts_prod/**/intent*.pkl", recursive=True)
    ))
    findings["intent"]["candidates"] = intent_pkls
    findings["intent"]["probes"] = [probe_pkl(p) for p in intent_pkls]
    if not intent_pkls:
        alerts.append("intent.pkl 未找到")
        missing.append({"need":"intent_pro_cal.pkl 或 artifacts/intent_*.pkl","where":"intent/**/artifacts 或 artifacts/","why":"啟用 ML 路線並做三路比較"})
except Exception as e:
    alerts.append(f"intent.probe: {type(e).__name__}: {e}")

# intent dataset
ds = Path("data/intent_eval/dataset.cleaned.jsonl")
if ds.exists():
    n, labels = 0, set()
    for ln in ds.read_text(encoding="utf-8", errors="replace").splitlines():
        if not ln.strip(): continue
        try:
            d = json.loads(ln)
            n += 1
            lab = d.get("label") or d.get("intent") or ""
            if lab!="": labels.add(str(lab))
        except Exception: pass
    findings["intent"]["dataset"] = {"path":str(ds),"n":n,"labels":sorted(labels)}
else:
    missing.append({"need":"dataset.cleaned.jsonl","where":"data/intent_eval/","why":"離線統一指標/混淆矩陣"})

# ===== 4) Spam =====
spam_pkls = sorted(set(glob.glob("artifacts/**/spam*.pkl", recursive=True) + glob.glob("artifacts_inbox/**/spam*.pkl", recursive=True)))
findings["spam"]["candidates"] = spam_pkls
ens = Path("artifacts_prod/ens_thresholds.json")
if ens.exists():
    try: findings["spam"]["ens_thresholds.json"] = json.loads(ens.read_text(encoding="utf-8"))
    except Exception as e: findings["spam"]["ens_thresholds.json"] = f"JSON_ERROR:{e}"
else:
    missing.append({"need":"ens_thresholds.json","where":"artifacts_prod/","why":"Spam 門檻校正重現"})

# ===== 5) KIE =====
kie_model_dirs = sorted({str(Path(p).parent) for p in glob.glob("artifacts_inbox/**/kie*/model", recursive=True)})
findings["kie"]["model_dirs"] = kie_model_dirs
gold = Path("data/kie_eval/gold_merged.jsonl")
for_eval = Path("data/kie/test_real.for_eval.jsonl")
if gold.exists(): 
    findings["kie"]["gold_merged_lines"] = sum(1 for _ in gold.open(encoding="utf-8", errors="ignore"))
else:
    missing.append({"need":"gold_merged.jsonl","where":"data/kie_eval/","why":"KIE 欄位級指標"})
if for_eval.exists():
    findings["kie"]["for_eval_lines"] = sum(1 for _ in for_eval.open(encoding="utf-8", errors="ignore"))
else:
    alerts.append("KIE for_eval 測資未見（可選）")

# ===== 6) Configs =====
cfgs = {
  "intent_rules_calib": sorted(glob.glob("**/intent_rules_calib*.json", recursive=True)),
  "kie_runtime_config": sorted(glob.glob("**/kie_runtime_config*.json", recursive=True)),
  "intent_contract":    sorted(glob.glob("**/intent_contract*.json", recursive=True)),
}
findings["configs"]["paths"]=cfgs
for key, lst in cfgs.items():
    if not lst:
        missing.append({"need":f"{key}.json","where":"專案內對應路徑","why":"對齊訓練/推論期契約"})
    else:
        f = Path(lst[0])
        try: findings["configs"][key] = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e: findings["configs"][key] = f"JSON_ERROR:{e}"

# ===== 7) DB（不自動 ALTER；缺表直接列缺）=====
dbp = Path("reports_auto/audit.sqlite3")
if dbp.exists():
    try:
        con = sqlite3.connect(dbp); cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tbls = [r[0] for r in cur.fetchall()]
        findings["db"]["tables"]=tbls
        for t in ("llm_calls","actions","mails"):
            if t not in tbls:
                alerts.append(f"DB 表缺失: {t}")
                missing.append({"need":t,"where":"reports_auto/audit.sqlite3","why":"審計與冪等紀錄"})
    except Exception as e:
        findings["db"]["error"]=f"{type(e).__name__}: {e}"
else:
    missing.append({"need":"audit.sqlite3","where":"reports_auto/","why":"審計/成本/延遲/行為結果"})

# ===== 8) 報告輸出（Markdown + JSON；不中斷；EXIT 0）=====
findings["alerts"]=alerts
(OUT/"probe_findings.json").write_text(json.dumps(findings,ensure_ascii=False,indent=2),encoding="utf-8")
req = {"please_provide": missing, "notes": alerts,
       "intent_models": findings["intent"].get("candidates",[]),
       "spam_models": findings["spam"].get("candidates",[]),
       "kie_models": findings["kie"].get("model_dirs",[])}
(OUT/"REQUEST_missing_items.json").write_text(json.dumps(req,ensure_ascii=False,indent=2),encoding="utf-8")

lines = [ "# 資料盤點與徵集報告",
          f"- 目錄: {OUT}",
          "## 待補清單（請回傳/放置）:" ]
for i,x in enumerate(missing,1):
    lines.append(f"{i}. **{x['need']}** → 放在 `{x['where']}` ；用途：{x['why']}")
lines += ["","## 重要提醒:"] + [f"- {a}" for a in alerts]
lines += ["","## Intent 模型候選:"] + [f"- {p}" for p in findings["intent"].get("candidates",[])]
lines += ["","## Spam 模型候選:"] + [f"- {p}" for p in findings["spam"].get("candidates",[])]
lines += ["","## KIE 模型目錄:"] + [f"- {p}" for p in findings["kie"].get("model_dirs",[])]
(Path(OUT/"REQUEST_missing_items.md")).write_text("\n".join(lines),encoding="utf-8")

print("[OK] probe done at", OUT, file=pylog)
PY

echo "[DONE] See ${OUT}/REQUEST_missing_items.{md,json} and probe_findings.json"
