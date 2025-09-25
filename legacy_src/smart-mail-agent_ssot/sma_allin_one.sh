#!/usr/bin/env bash
# sma_allin_one.sh — 一鍵：環境(.venv_clean)→相容補丁→RAG建索引/查詢→Spam/Intent/KIE管線→嚴格守門
# 產物：reports_auto/oneclick/<ts>/{logs,status}；失敗一定產生 CRASH 並更新 LAST_CRASH_PATH.txt
set -u
umask 022

# ---------- 參數 ----------
ROOT_ARG=""
while [ $# -gt 0 ]; do case "$1" in --root) ROOT_ARG="$2"; shift 2 ;; *) shift ;; esac; done
to_linux() { case "$1" in \\\\wsl.localhost\\*) s="${1#\\\\wsl.localhost\\}"; s="${s#*\\}"; printf '/%s\n' "${s//\\//}";; *) printf '%s\n' "$1";; esac; }

if [ -n "$ROOT_ARG" ]; then ROOT="$(to_linux "$ROOT_ARG")"
elif git rev-parse --show-toplevel >/dev/null 2>&1; then ROOT="$(git rev-parse --show-toplevel)"
else ROOT="$PWD"; fi
cd "$ROOT" 2>/dev/null || true

TS="$(date +%Y%m%dT%H%M%S)"
OUT="$ROOT/reports_auto/oneclick/$TS"; LOG="$OUT/logs"; STS="$OUT/status"
mkdir -p "$LOG" "$STS" "$ROOT/reports_auto"/{logs,crash_bundles,kb/faiss_index} src/smart_mail_agent/{cli,rag,ml,pipeline} samples/inbox 2>/dev/null || true
ln -sfn "$OUT" "$ROOT/reports_auto/oneclick/LATEST" 2>/dev/null || true
RUN_LOG="$LOG/ALLIN_${TS}.log"; exec > >(tee -a "$RUN_LOG") 2>&1

echo "[INFO] ROOT=$ROOT"; echo "[INFO] OUT=$OUT"

# ---------- 0) venv 只用 .venv_clean ----------
if [ ! -x .venv_clean/bin/python ]; then python3 -m venv .venv_clean || true; fi
. .venv_clean/bin/activate 2>/dev/null || true
python -m pip install -U pip wheel setuptools >/dev/null 2>&1 || true
# 優先 requirements.txt；不足再補
if [ -f requirements.txt ]; then pip install -q -r requirements.txt >/dev/null 2>&1 || true; fi
pip install -q faiss-cpu langchain langchain-community langchain-openai openai tiktoken langchain-text-splitters >/dev/null 2>&1 || true
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
: > src/smart_mail_agent/__init__.py; : > src/smart_mail_agent/cli/__init__.py; : > src/smart_mail_agent/rag/__init__.py; : > src/smart_mail_agent/ml/__init__.py

# ---------- 1) RAG 相容層 + HashEmb（繼承 Embeddings，避免警告） ----------
cat > src/smart_mail_agent/rag/compat.py <<'PY'
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except Exception:
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
    except Exception:
        from langchain.text_splitters import RecursiveCharacterTextSplitter
try:
    from langchain_community.vectorstores import FAISS
except Exception:
    from langchain.vectorstores import FAISS
PY
cat > src/smart_mail_agent/rag/provider.py <<'PY'
from typing import List
import hashlib
try:
    from langchain_core.embeddings import Embeddings
except Exception:
    class Embeddings:  # type: ignore
        def embed_documents(self, texts: List[str]) -> List[List[float]]: ...
        def embed_query(self, text: str) -> List[float]: ...
class HashEmb(Embeddings):
    def __init__(self, dim: int = 384) -> None: self.dim = dim
    def _vec(self, t: str) -> List[float]:
        b = hashlib.sha1((t or "").encode("utf-8")).digest()
        return [ b[i % len(b)] / 255.0 for i in range(self.dim) ]
    def embed_documents(self, texts: List[str]) -> List[List[float]]: return [ self._vec(t) for t in texts ]
    def embed_query(self, text: str) -> List[float]: return self._vec(text)
PY

# ---------- 2) 覆寫 RAG CLI（index_name=kb；無語料自動收集） ----------
cat > src/smart_mail_agent/cli/rag_build.py <<'PY'
import os, json, pathlib
from smart_mail_agent.rag.compat import RecursiveCharacterTextSplitter, FAISS
from smart_mail_agent.rag.provider import HashEmb
ROOT = pathlib.Path("."); IDX = ROOT / "reports_auto/kb/faiss_index"; IDX.mkdir(parents=True, exist_ok=True)
NAME = os.getenv("SMA_KB_INDEX_NAME","kb")
USE_OPENAI = bool(os.getenv("OPENAI_API_KEY"))
if USE_OPENAI:
    from langchain_openai import OpenAIEmbeddings; emb = OpenAIEmbeddings(model="text-embedding-3-small")
else:
    emb = HashEmb()
def main():
    data = ROOT / "reports_auto/kb/src"; data.mkdir(parents=True, exist_ok=True)
    if not any(data.iterdir()):
        exts={".md",".txt",".py",".rst",".yaml",".yml"}; n=0
        for p in ROOT.rglob("*"):
            if p.suffix.lower() in exts and p.is_file() and p.stat().st_size<=256*1024:
                try: (data/p.name).write_text(p.read_text(encoding="utf-8",errors="ignore")[:20000], encoding="utf-8"); n+=1
                except Exception: pass
            if n>=40: break
    sp = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    texts, metas = [], []
    for f in sorted(data.glob("*")):
        if not f.is_file(): continue
        try: raw = f.read_text(encoding="utf-8", errors="ignore")
        except Exception: continue
        for i,ch in enumerate(sp.split_text(raw)): texts.append(ch); metas.append({"source": str(f), "chunk": i})
    out={"ok":True,"files":len(list(data.glob('*'))),"chunks":len(texts),"index_dir":str(IDX),"index_name":NAME,"use_openai":USE_OPENAI}
    if texts:
        try: vs = FAISS.from_texts(texts=texts, embedding=emb, metadatas=metas)
        except TypeError: vs = FAISS.from_texts(texts, emb, metadatas=metas)
        vs.save_local(IDX, index_name=NAME); out["saved"]=[f"{NAME}.faiss",f"{NAME}.pkl"]
    print(json.dumps(out, ensure_ascii=False))
if __name__=="__main__": main()
PY
cat > src/smart_mail_agent/cli/rag_query.py <<'PY'
import os, json, argparse, pathlib
from smart_mail_agent.rag.compat import FAISS
from smart_mail_agent.rag.provider import HashEmb
def _preview(t: str, n: int=160)->str: return " ".join((t or "").splitlines())[:n]
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("q", nargs="?", default="付款條件是什麼？")
    ap.add_argument("--index", default="reports_auto/kb/faiss_index"); a=ap.parse_args()
    ROOT=pathlib.Path("."); idx=ROOT/a.index; idx.mkdir(parents=True, exist_ok=True)
    name=os.getenv("SMA_KB_INDEX_NAME","kb")
    if not (idx/f"{name}.faiss").exists() and (idx/"index.faiss").exists(): name="index"
    if bool(os.getenv("OPENAI_API_KEY")):
        from langchain_openai import OpenAIEmbeddings; emb=OpenAIEmbeddings(model="text-embedding-3-small")
    else:
        emb=HashEmb()
    vs=FAISS.load_local(idx, embeddings=emb, index_name=name, allow_dangerous_deserialization=True)
    docs=vs.similarity_search(a.q, k=4)
    lines=[f"- {d.metadata.get('source')}: {_preview(d.page_content)}" for d in docs]
    print(json.dumps({"kb_hits":len(docs),"index_name":name,"answer":"\n".join(lines)}, ensure_ascii=False))
if __name__=="__main__": main()
PY

# ---------- 3) 三模型 stub（若你已有真模型，這段不會影響你的檔） ----------
if [ ! -s src/smart_mail_agent/ml/infer.py ]; then
  cat > src/smart_mail_agent/ml/infer.py <<'PY'
import re, json, time
from typing import Dict, Any
def _now(): return time.strftime("%Y-%m-%dT%H:%M:%S")
def predict_spam(text:str)->Dict[str,Any]:
    kws=["buy now","免費","點我","限定","優惠","bitcoin","usdt","博彩"]; s=0.1+0.2*sum(k in (text or "").lower() for k in kws)
    return {"ok":True,"model":"stub-spam","label":"spam" if s>=0.5 else "ham","score":round(min(s,1.0),3),"ts":_now()}
def predict_intent(text:str)->Dict[str,Any]:
    t=(text or "").lower(); it="other"
    it="quote" if any(k in t for k in ["報價","quote","價格","費用"]) else it
    it="faq" if any(k in t for k in ["faq","保固","出貨","付款"]) else it
    it="invoice" if any(k in t for k in ["發票","抬頭","統編","invoice"]) else it
    return {"ok":True,"model":"stub-intent","intent":it,"score":0.75,"ts":_now()}
def extract_kie(text:str)->Dict[str,Any]:
    m_amt=re.search(r"(?:NT\\$|USD\\$|\\$)\\s?([0-9][0-9,\\.]+)", text or "", re.I)
    m_ord=re.search(r"(?:order|訂單)[\\s#:]*([A-Z0-9\\-]{6,})", text or "", re.I)
    return {"ok":True,"model":"stub-kie","fields":{"amount":m_amt.group(1) if m_amt else None,"order_id":m_ord.group(1) if m_ord else None,"has_invoice":bool(re.search(r"發票|invoice", text or "", re.I))},"ts":_now()}
def smoke_all()->Dict[str,Any]:
    s="您好，想詢問報價與付款方式，金額約 NT$12,500。訂單號：ORDER-ABCD1234。"
    return {"spam":predict_spam(s),"intent":predict_intent(s),"kie":extract_kie(s),"ts":_now()}
if __name__=="__main__": print(json.dumps(smoke_all(), ensure_ascii=False, indent=2))
PY
fi

# ---------- 4) RAG 建索引 & 查詢（落檔，不因錯誤退出） ----------
BUILD_LOG="$LOG/rag_build_${TS}.log"; QUERY_LOG="$LOG/rag_query_${TS}.log"
rm -f reports_auto/kb/faiss_index/kb.faiss reports_auto/kb/faiss_index/kb.pkl 2>/dev/null || true
python -m smart_mail_agent.cli.rag_build  > "$BUILD_LOG" 2>&1 || true
python -m smart_mail_agent.cli.rag_query "付款條件是什麼？" > "$QUERY_LOG" 2>&1 || true
if grep -q '"kb_hits"' "$QUERY_LOG"; then echo "OK" > "$STS/RAG_PASS_${TS}.txt"; echo "[PASS] RAG 查詢完成：$QUERY_LOG"; else
  C="$ROOT/reports_auto/crash_bundles/$TS"; mkdir -p "$C"; CL="$C/CRASH_RAG_${TS}.log"
  { echo "[CRASH] RAG ts=$TS root=$ROOT"; echo "===== BUILD (tail) ====="; tail -n 120 "$BUILD_LOG"; echo "===== QUERY (head) ====="; sed -n '1,120p' "$QUERY_LOG"; } > "$CL"
  cp -f "$CL" "$LOG/"; echo "$CL" > "$ROOT/reports_auto/logs/LAST_CRASH_PATH.txt"; echo "[FAIL] RAG 失敗，CRASH：$CL"
fi

# ---------- 5) 管線（Spam/Intent/KIE）+ 嚴格守門 ----------
cat > src/smart_mail_agent/pipeline/pipe_run.py <<'PY'
import json, time, pathlib, traceback
from typing import List, Dict, Any
from smart_mail_agent.ml import infer
R=pathlib.Path("."); OUT=R/"reports_auto"; LOG=OUT/"logs"; STS=OUT/"status"; CR=OUT/"crash_bundles"; INB=R/"samples/inbox"
def ts(): return time.strftime("%Y%m%dT%H%M%S")
def ensure_inbox():
    INB.mkdir(parents=True, exist_ok=True)
    if not any(INB.glob("*.txt")):
        ss=["【業務詢價】想詢問報價與付款方式，金額 NT$12,500，訂單號 ORDER-ABCD1234，需三聯發票。",
            "請問出貨時間與運費？付款條件可以月結嗎？","限時優惠！點我領取 9 折券，買越多省越多。",
            "我要索取正式發票，抬頭與統編如下：XXX股份有限公司 12345678","Send a quote for 100 units and payment terms.",
            "需要保固條款與退換貨 FAQ。","請問是否支援對公轉帳？我們的 PO 將於下週釋出。","出貨需附隨貨明細，金額約 NT$7,788；請確認付款方式。",
            "恭喜中獎！USDT 投資回饋計畫，立即買入。","前次詢價，是否可提供折扣與交期？"]
        for i,t in enumerate(ss,1): (INB/f"mail_{i:02d}.txt").write_text(t,encoding="utf-8")
def read_inbox()->List[Dict[str,Any]]:
    return [{"id":p.stem,"path":str(p),"text":p.read_text(encoding="utf-8",errors="ignore")} for p in sorted(INB.glob("*.txt"))]
def handle(m:Dict[str,Any])->Dict[str,Any]:
    try:
        sp=infer.predict_spam(m["text"]); it=infer.predict_intent(m["text"])
        kie=infer.extract_kie(m["text"]) if it.get("intent") in {"quote","invoice","faq"} else {"ok":True,"fields":{}}
        return {"id":m["id"],"status":"done","spam":sp,"intent":it,"kie":kie}
    except Exception as e:
        return {"id":m.get("id","?"),"status":"error","error":{"type":e.__class__.__name__,"msg":str(e),"trace":traceback.format_exc(limit=2)}}
def gate(xs:List[Dict[str,Any]])->Dict[str,int]:
    d={"done":0,"error":0,"queued":0}
    for a in xs: d[a.get("status","queued")]=d.get(a.get("status","queued"),0)+1
    return d
def main():
    TS=ts(); ensure_inbox(); xs=[handle(m) for m in read_inbox()[:10]]
    LOG.mkdir(parents=True,exist_ok=True); STS.mkdir(parents=True,exist_ok=True); CR.mkdir(parents=True,exist_ok=True)
    act=STS/f"ACTIONS_{TS}.jsonl"
    with act.open("w",encoding="utf-8") as f:
        for a in xs: f.write(json.dumps(a,ensure_ascii=False)+"\n")
    dist=gate(xs); summ={"ts":TS,"inbox_count":len(list(INB.glob('*.txt'))),"evaluated":len(xs),"distribution":dist,"pass_rule":"done=10,error=0,queued=0","actions_jsonl":str(act)}
    (STS/f"PIPE_SUMMARY_{TS}.json").write_text(json.dumps(summ,ensure_ascii=False,indent=2),encoding="utf-8")
    ok=(dist.get("done",0)==10 and dist.get("error",0)==0 and dist.get("queued",0)==0)
    if ok:
        (STS/f"PASS_PIPE_{TS}.txt").write_text("OK",encoding="utf-8"); print(json.dumps({"ok":True,**summ},ensure_ascii=False))
    else:
        cd=CR/TS; cd.mkdir(parents=True,exist_ok=True); cl=cd/f"CRASH_PIPE_{TS}.log"
        cl.write_text("[GATE_FAIL] distribution="+json.dumps(dist,ensure_ascii=False)+"\nExpect: done=10,error=0,queued=0\nACTIONS="+str(act)+"\n",encoding="utf-8")
        (OUT/"logs"/"LAST_CRASH_PATH.txt").write_text(str(cl),encoding="utf-8"); print(json.dumps({"ok":False,**summ,"crash_log":str(cl)},ensure_ascii=False))
if __name__=="__main__": main()
PY

PIPE_LOG="$LOG/PIPE_${TS}.log"
python -m smart_mail_agent.pipeline.pipe_run > "$PIPE_LOG" 2>&1 || true

# ---------- 6) 摘要 ----------
echo; echo "==== SUMMARY ===="; echo "ROOT: $ROOT"; echo "OUT : $OUT"
echo "RAG_BUILD_LOG: $BUILD_LOG"; echo "RAG_QUERY_LOG: $QUERY_LOG"; echo "PIPE_LOG: $PIPE_LOG"
[ -f "$ROOT/reports_auto/logs/LAST_CRASH_PATH.txt" ] && echo "LAST_CRASH: $(cat "$ROOT/reports_auto/logs/LAST_CRASH_PATH.txt")" || true
echo "Open this folder: $OUT"
