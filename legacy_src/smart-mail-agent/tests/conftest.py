import io, json, runpy, sys, types, time
from pathlib import Path
import builtins
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/"scripts"))
sys.path.insert(0, str(ROOT/".sma_tools"))

@pytest.fixture(autouse=True)
def _fix_env(monkeypatch, tmp_path):
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("PYTHONNOUSERSITE", "1")
    monkeypatch.setenv("PYTHONPATH", f".:scripts:.sma_tools:{sys.path[0]}")
    (ROOT/"reports_auto/logs").mkdir(parents=True, exist_ok=True)

@pytest.fixture
def tiny_spam_jsonl(tmp_path):
    p = tmp_path/"spam.jsonl"
    rows = [
        {"id":"h1","subject":"hello","body":"see you","label":"ham"},
        {"id":"s1","subject":"verify account","body":"click http://bad.xyz","label":"spam"},
        {"id":"h2","subject":"lunch","body":"12?","label":"ham"},
        {"id":"s2","subject":"urgent invoice","body":"pay now http://bad.top","label":"spam"},
    ]
    p.write_text("\n".join(json.dumps(r,ensure_ascii=False) for r in rows), encoding="utf-8")
    return p

@pytest.fixture
def tiny_thresholds(tmp_path):
    t = tmp_path/"thr.json"
    t.write_text(json.dumps({"threshold":0.4,"signals_min":2}), encoding="utf-8")
    return t

# ---- Fake Spam/Intent Models -------------------------------------------------
class _FakeSpamModel:
    def predict_proba(self, X):
        # ham/spam 二類；看到 verify/invoice/url 就高分
        out=[]
        for x in X:
            v=x.lower()
            p1 = 0.9 if ("verify" in v or "invoice" in v or "http" in v) else 0.1
            out.append([1-p1, p1])
        return __import__("numpy").array(out)

class _FakeIntentModel:
    labels = ["biz_quote","tech_support","complaint","policy_qa","profile_update","other"]
    def predict_proba(self, X):
        import numpy as np
        out=[]
        for x in X:
            v=x.lower()
            vec=[0,0,0,0,0,0]
            if "quote" in v or "nt$" in v: vec[0]=0.9
            elif "cannot login" in v or "error" in v: vec[1]=0.9
            elif "refund" in v or "angry" in v: vec[2]=0.9
            elif "policy" in v or "terms" in v: vec[3]=0.9
            elif "update phone" in v or "change address" in v: vec[4]=0.9
            else: vec[5]=0.9
            # 剩餘均分
            s=sum(vec); vec=[v if v>0 else (1-s)/5 for v in vec]
            out.append(vec)
        return np.array(out)

@pytest.fixture
def fake_joblib(monkeypatch):
    # 讓 joblib.load 回傳 Fake 模型
    jl = types.SimpleNamespace()
    jl.load = lambda *_args, **_kw: _FakeIntentModel()
    monkeypatch.setitem(sys.modules, "joblib", jl)
    return jl

# ---- Fake transformers（避免安裝 HuggingFace/torch） -----------------------
class _FakeTok:
    def __init__(self): self.name="fake-tok"
    def __call__(self, text, return_offsets_mapping=True, truncation=True, max_length=512):
        # 極簡 offset：把每個字元當一 token；有助測 KIE 解碼
        offs=[(0,0)]  # special
        for i,ch in enumerate(text):
            offs.append((i,i+1))
        ids=list(range(len(offs)))
        att=[1]*len(offs)
        return {"input_ids":ids, "attention_mask":att, "offset_mapping":offs}
    def save_pretrained(self, out): Path(out).mkdir(parents=True, exist_ok=True)

class _FakeKIEModel:
    class Cfg:
        id2label = ["O","B-amount","I-amount","B-date_time","I-date_time","B-env","I-env","B-sla","I-sla"]
        num_labels = 9
    config = Cfg()
    def eval(self): return self
    @property
    def logits(self): return None
    def __call__(self, *a, **k):
        import numpy as np, types
        # 簡單規則：遇到數字串 -> amount；遇到 yyyy-mm-dd -> date；env/sla 關鍵字
        input_ids=a[0][0] if a else list(range(10))
        L=len(input_ids)
        # 預設 all "O"
        arr = np.zeros((L, 9))
        # 造一點 span 命中：為測試 decode 流水即可
        # 實際 logits 不重要，argmax 位置才重要
        # 讓 index 5~8 為 I 系列
        for i in range(1, min(L, 6)):
            arr[i][0]=1.0
        class O: pass
        o=O(); o.logits=__import__("numpy").array([arr])
        return o
    def save_pretrained(self, out): Path(out).mkdir(parents=True, exist_ok=True)

class _FakeTFM(types.ModuleType):
    def __init__(self):
        super().__init__("transformers")
        self.AutoTokenizer = types.SimpleNamespace(from_pretrained=lambda *a, **k: _FakeTok())
        self.AutoModelForTokenClassification = types.SimpleNamespace(from_pretrained=lambda *a, **k: _FakeKIEModel())
        self.DataCollatorForTokenClassification = object
        self.Trainer = object
        self.TrainingArguments = object
        self.set_seed = lambda *_: None

@pytest.fixture(autouse=True)
def fake_transformers(monkeypatch):
    # 在測試中先注入假的 transformers，再 import 相關腳本
    if "transformers" not in sys.modules:
        sys.modules["transformers"] = _FakeTFM()
    yield
    # 不恢復也可；測試進程內保持 fake

# ---- 共用小工具 -------------------------------------------------------------
def run_script(path: Path, argv: list[str]):
    import sys
    old = sys.argv[:]
    try:
        sys.argv = [str(path)] + argv
        runpy.run_path(str(path), run_name="__main__")
    finally:
        sys.argv = old
