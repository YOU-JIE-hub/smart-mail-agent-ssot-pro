from __future__ import annotations

import argparse
import json


def _heuristic_spam_score(text: str) -> float:
    if not text:
        return 0.0
    lowers = text.lower()
    kws = [
        "free",
        "winner",
        "bitcoin",
        "viagra",
        "casino",
        "loan",
        "credit",
        "limited time",
        "act now",
        "click here",
        "http://",
        "https://",
        "獎",
        "中獎",
        "免費",
        "限時",
        "點擊",
        "投資",
        "加密",
        "博彩",
    ]
    score = 0.0
    for k in kws:
        if k in lowers:
            score += 0.08
    if "http://" in lowers or "https://" in lowers:
        score += 0.10
    return min(score, 0.99)


def _classify(subject: str, content: str, sender: str | None = None) -> dict:
    text = f"{subject}\n{content}\n{sender or ''}"
    score = _heuristic_spam_score(text)
    return {
        "subject": subject,
        "sender": sender,
        "score": round(score, 2),
        "is_spam": score >= 0.5,
        "engine": "heuristic-v0",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="sma-spamcheck",
        description="垃圾信偵測（輕量 CLI 包裝器，可替換為正式 orchestrator）",
    )
    ap.add_argument("--subject", required=True)
    ap.add_argument("--content", required=True)
    ap.add_argument("--sender")
    ap.add_argument("--json", action="store_true", help="輸出 JSON（預設為人讀格式）")
    args = ap.parse_args(argv)

    res = _classify(args.subject, args.content, args.sender)
    if args.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(
            f"subject={res['subject']!r} sender={res['sender']!r} "
            f"is_spam={res['is_spam']} score={res['score']} engine={res['engine']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
