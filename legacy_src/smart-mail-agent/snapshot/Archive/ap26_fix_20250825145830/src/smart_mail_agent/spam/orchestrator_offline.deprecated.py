# deprecated; use spam_filter_orchestrator.py
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import rules as _rules


@dataclass
class Thresholds:
    link_ratio_drop: float = 0.50
    link_ratio_review: float = 0.30


def _boolish_rule_out(x: Any) -> bool:
    if isinstance(x, bool):
        return x
    if isinstance(x, dict):
        for k in ("hit", "match", "is_spam", "spam", "value", "ok", "result"):
            if k in x:
                return bool(x[k])
        return False
    return bool(x)


def _call_rule(rule: Callable, payload: Dict[str, Any]) -> bool:
    try:
        out = rule(payload)  # type: ignore[arg-type]
    except TypeError:
        out = rule(payload.get("content", ""))  # type: ignore[arg-type]
    return _boolish_rule_out(out)


def _normalize_model_out(x: Any) -> Tuple[Optional[float], Optional[str]]:
    if x is None:
        return None, None
    if isinstance(x, (int, float)):
        v = float(x)
        return (v if 0.0 <= v <= 1.0 else None), None
    if isinstance(x, str):
        lab = x.lower().strip()
        return (None, lab) if lab in {"spam", "ham"} else (None, None)
    if isinstance(x, tuple) and len(x) == 2:
        a, b = x
        if isinstance(a, (int, float)) and isinstance(b, str):
            return float(a), b.lower()
        if isinstance(a, str) and isinstance(b, (int, float)):
            return float(b), a.lower()
        return None, None
    if isinstance(x, dict):
        lab = x.get("label")
        sc = x.get("score")
        return (
            float(sc) if isinstance(sc, (int, float)) else None,
            lab.lower() if isinstance(lab, str) else None,
        )
    if isinstance(x, list) and x:
        # 重要修正：對 list[dict]，若元素含 label 與 score，要**保留標籤**。
        best_score: Optional[float] = None
        best_label: Optional[str] = None
        first_label: Optional[str] = None
        for it in x:
            if not isinstance(it, dict):
                continue
            if first_label is None and isinstance(it.get("label"), str):
                first_label = it["label"].lower()
            sc = it.get("score")
            lab = it.get("label")
            if isinstance(sc, (int, float)):
                scf = float(sc)
                if (best_score is None) or (scf > best_score):
                    best_score = scf
                    best_label = lab.lower() if isinstance(lab, str) else None
        if best_score is not None:
            # 回傳(最高分, 對應的標籤或 None)
            return best_score, best_label
        if first_label:
            # 沒有分數就回第一個標籤
            return None, first_label
    return None, None


def _invoke_model_variants(
    model: Callable[..., Any], subject: str, content: str
) -> List[Tuple[Optional[float], Optional[str]]]:
    """
    兼容 2 參數與 1 參數模型；先試 (subject, content) 再試 (subject)。
    """
    outs: List[Tuple[Optional[float], Optional[str]]] = []
    tried_any = False
    try:
        tried_any = True
        outs.append(_normalize_model_out(model(subject, content)))  # type: ignore[misc]
    except TypeError:
        pass
    try:
        tried_any = True
        outs.append(_normalize_model_out(model(subject)))  # type: ignore[misc]
    except TypeError:
        pass
    return outs if tried_any else []


class SpamFilterOrchestratorOffline:
    def __init__(self, thresholds: Optional[Thresholds] = None) -> None:
        self.thresholds = thresholds or Thresholds()

    def decide(
        self, subject: str, html_or_text: str, *, model: str | None = None
    ) -> Dict[str, Any]:
        text_all = f"{subject or ''}\n{html_or_text or ''}"

        reasons: list[str] = []
        if "\u200b" in text_all:
            return {
                "action": "route",
                "reasons": ["zwsp"],
                "scores": {"link_ratio": 0.0},
                "model": model or "offline",
            }

        ratio = _rules.link_ratio(text_all)
        if ratio >= self.thresholds.link_ratio_drop:
            reasons.append(f"rule:link_ratio>={self.thresholds.link_ratio_drop:.2f}")
            return {
                "action": "drop",
                "reasons": reasons,
                "scores": {"link_ratio": float(ratio)},
                "model": model or "offline",
            }
        if ratio >= self.thresholds.link_ratio_review:
            reasons.append(f"rule:link_ratio>={self.thresholds.link_ratio_review:.2f}")
            return {
                "action": "review",
                "reasons": reasons,
                "scores": {"link_ratio": float(ratio)},
                "model": model or "offline",
            }

        if _rules.contains_keywords(text_all):
            return {
                "action": "drop",
                "source": "keyword",
                "reasons": ["rule:keyword"],
                "scores": {"link_ratio": float(ratio)},
                "model": model or "offline",
            }

        return {
            "action": "route",
            "reasons": reasons,
            "scores": {"link_ratio": float(ratio)},
            "model": model or "offline",
        }


@dataclass
class OrchestrationResult:
    is_spam: bool
    score: Optional[float]
    source: str
    action: str
    is_borderline: bool
    extra: Optional[Dict[str, Any]] = None


def orchestrate(
    subject: str,
    rule: Callable[[Any], Any],
    model: Optional[Callable[..., Any]] = None,
    *,
    model_threshold: float = 0.6,
) -> OrchestrationResult:
    """
    規則先決；模型規則：
      - 任一 variant 標籤 'ham' => ham/route_to_inbox（優先，忽略分數）
      - 任一 variant 標籤 'spam'：
          score < thr -> ham；=thr -> review；>thr -> drop
          無 score -> drop
      - 僅分數 -> 分數 >= thr -> spam(=thr 視為 borderline->review)，否則 ham
      - 模型不可呼叫 -> fallback ham
      - 無模型 -> default ham
    """
    payload = {"subject": subject, "content": subject}

    try:
        if _call_rule(rule, payload):
            return OrchestrationResult(
                is_spam=True, score=1.0, source="rule", action="drop", is_borderline=False
            )
    except Exception:
        pass

    if model is not None:
        try:
            variants = _invoke_model_variants(model, subject, subject)
            if variants:
                eps = 1e-12
                # 先看 ham（有標籤就直接信任）
                ham_items = [v for v in variants if v[1] == "ham"]
                if ham_items:
                    return OrchestrationResult(
                        is_spam=False,
                        score=ham_items[0][0],
                        source="model",
                        action="route_to_inbox",
                        is_borderline=False,
                    )
                # 再看 spam（有標籤才走這條）
                spam_items = [v for v in variants if v[1] == "spam"]
                if spam_items:
                    sc = spam_items[0][0]
                    if sc is None:
                        return OrchestrationResult(
                            is_spam=True,
                            score=None,
                            source="model",
                            action="drop",
                            is_borderline=False,
                        )
                    if sc < model_threshold - eps:
                        return OrchestrationResult(
                            is_spam=False,
                            score=sc,
                            source="model",
                            action="route_to_inbox",
                            is_borderline=False,
                        )
                    is_borderline = abs(sc - model_threshold) < eps
                    return OrchestrationResult(
                        is_spam=True,
                        score=sc,
                        source="model",
                        action=("review" if is_borderline else "drop"),
                        is_borderline=is_borderline,
                    )
                # 僅分數
                scores = [v[0] for v in variants if v[0] is not None]
                if scores:
                    sc = float(max(scores))
                    is_borderline = abs(sc - model_threshold) < eps
                    is_spam = sc >= model_threshold
                    return OrchestrationResult(
                        is_spam=is_spam,
                        score=sc,
                        source="model",
                        action=(
                            "review"
                            if (is_spam and is_borderline)
                            else ("drop" if is_spam else "route_to_inbox")
                        ),
                        is_borderline=is_borderline,
                    )
                # 全不可判 -> ham
                return OrchestrationResult(
                    is_spam=False,
                    score=None,
                    source="model",
                    action="route_to_inbox",
                    is_borderline=False,
                )
            # 模型完全呼叫不上
            return OrchestrationResult(
                is_spam=False,
                score=None,
                source="fallback",
                action="route_to_inbox",
                is_borderline=False,
                extra={"model_error": "model could not be invoked"},
            )
        except Exception as e:
            return OrchestrationResult(
                is_spam=False,
                score=None,
                source="fallback",
                action="route_to_inbox",
                is_borderline=False,
                extra={"model_error": str(e)},
            )

    return OrchestrationResult(
        is_spam=False, score=None, source="default", action="route_to_inbox", is_borderline=False
    )


def _main() -> int:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--subject", required=True)
    p.add_argument("--content", default="")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    res = SpamFilterOrchestratorOffline().decide(args.subject, args.content)
    if args.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(res)
    return 0
