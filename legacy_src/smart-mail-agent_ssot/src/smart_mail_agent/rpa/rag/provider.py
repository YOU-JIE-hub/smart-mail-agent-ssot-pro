from __future__ import annotations
import os, re, time, json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Tuple

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None

@dataclass
class Citation:
    doc_id: str
    snippet: str
    score: float
    url: Optional[str] = None

@dataclass
class AnswerResult:
    answer_md: str
    citations: List[Citation]
    confidence: float
    model: Optional[str] = None
    latency_ms: Optional[int] = None

class AnswerProvider:
    def answer(self, question: str, top_k: int = 3) -> AnswerResult:
        raise NotImplementedError

class _NaiveRetriever:
    def __init__(self, root: Path):
        self.root = root
        self.docs: List[Tuple[str, str]] = []
        self._load()
    def _load(self):
        kdir = self.root / "knowledge"
        files = list(kdir.glob("*.md")) if kdir.is_dir() else []
        if not files:
            fallback = self.root / "smart-mail-agent-core-main" / "data" / "knowledge" / "faq.md"
            if fallback.exists():
                files = [fallback]
        for p in files:
            try:
                self.docs.append((p.name, p.read_text(encoding="utf-8", errors="ignore")))
            except Exception:
                pass
        if not self.docs:
            self.docs.append(("faq_fallback.md",
                              "# 常見問題\n\n- 退款：7 天內申請並附訂單。\n- 資料變更：提供舊新值以利審核。\n- SLA：P1 30 分內回覆，4 小時內恢復。\n"))
    def _score(self, text: str, q: str) -> float:
        q_terms = [t for t in re.split(r"[^\w\u4e00-\u9fff]+", q.lower()) if t]
        if not q_terms: return 0.0
        t_low = text.lower()
        base = sum(t_low.count(t) for t in q_terms)
        bonus = 2.0 if " ".join(q_terms) in t_low else 0.0
        norm = max(50.0, len(text)/500.0)
        return (base + bonus)/norm
    def retrieve(self, q: str, top_k: int = 3) -> List[Citation]:
        scored: List[Tuple[Citation,float]] = []
        for doc_id, text in self.docs:
            s = self._score(text, q)
            if s <= 0: continue
            snippet = text[:400]
            m = re.search(re.escape(q.split()[0]) if q.split() else r".", text, flags=re.IGNORECASE)
            if m:
                start = max(0, m.start()-120); end = min(len(text), m.end()+200)
                snippet = text[start:end]
            scored.append((Citation(doc_id=doc_id, snippet=snippet.strip(), score=float(s)), s))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [c for c,_ in scored[:top_k]]

class OpenAIRAGProvider(AnswerProvider):
    def __init__(self, project_root: Optional[Path] = None, model: str = "gpt-4o-mini"):
        self.root = project_root or Path(".").resolve()
        self.retriever = _NaiveRetriever(self.root)
        self.model = model
        self.has_llm = bool(os.environ.get("OPENAI_API_KEY")) and (OpenAI is not None)
    def _llm(self, question: str, citations: List[Citation]) -> Tuple[str, float, Optional[int], Optional[str]]:
        if not self.has_llm:
            body = ["**回答（離線）**", "", question, "", "**依據資料**："]
            for c in citations: body.append(f"- {c.doc_id}（score={c.score:.3f}）")
            return "\n".join(body), 0.55, None, None
        client = OpenAI()
        system = ("你是客服助理。根據引用片段回答；找不到就誠實說明需要更多資訊。"
                  "回答用繁體中文、分段、列出來源檔名。")
        ctx = "\n\n".join([f"[{i+1}] {c.doc_id}\n{c.snippet}" for i,c in enumerate(citations)])
        user = f"問題：{question}\n\n引用：\n{ctx}\n\n請回答並在結尾列出使用到的來源編號。"
        t0 = time.time()
        try:
            rsp = client.responses.create(
                model=self.model,
                input=[{"role":"system","content":system},{"role":"user","content":user}],
                temperature=0.2,
            )
            txt = rsp.output_text
            latency = int((time.time()-t0)*1000)
            return txt, 0.82, latency, self.model
        except Exception:
            latency = int((time.time()-t0)*1000)
            body = ["**回答（降級）**", "", question, "", "**依據資料**："]
            for c in citations: body.append(f"- {c.doc_id}（score={c.score:.3f}）")
            return "\n".join(body), 0.60, latency, None
    def answer(self, question: str, top_k: int = 3) -> AnswerResult:
        citations = self.retriever.retrieve(question, top_k=top_k) or []
        ans_md, conf, latency, model = self._llm(question, citations)
        return AnswerResult(answer_md=ans_md, citations=citations, confidence=conf, model=model, latency_ms=latency)

def answer_as_json(provider: AnswerProvider, question: str, top_k: int = 3) -> str:
    res = provider.answer(question, top_k=top_k)
    payload = {
        "answer_md": res.answer_md,
        "citations": [asdict(c) for c in res.citations],
        "confidence": res.confidence,
        "model": res.model,
        "latency_ms": res.latency_ms,
    }
    return json.dumps(payload, ensure_ascii=False)
