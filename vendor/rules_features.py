"""
零參數特徵工廠，確保與序列化相容。
後續要擴充特徵，請只在此檔新增，並同步更新 features.schema.json。
"""
from __future__ import annotations
import hashlib, json
from typing import Iterable, List, Any
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.preprocessing import FunctionTransformer
from sklearn.feature_extraction.text import TfidfVectorizer

def _to_text_list(X: Any) -> List[str]:
    # 支援 X 為 list[str] 或 list[dict]（取 text/subject+body）
    out: List[str] = []
    if isinstance(X, list):
        for e in X:
            if isinstance(e, str):
                out.append(e)
            elif isinstance(e, dict):
                if "text" in e: out.append(str(e["text"]))
                elif "body" in e and "subject" in e: out.append(str(e["subject"]) + " " + str(e["body"]))
                else: out.append(json.dumps(e, ensure_ascii=False))
            else:
                out.append(str(e))
    else:
        out = [str(X)]
    return out

def _tfidf_block(ngram=(1,2), min_df=2, max_df=0.9, analyzer="word"):
    return Pipeline([
        ("to_text", FunctionTransformer(_to_text_list, validate=False)),
        ("tfidf", TfidfVectorizer(ngram_range=ngram, min_df=min_df, max_df=max_df, analyzer=analyzer))
    ])

def rules_feat():
    """
    零參數；回傳 FeatureUnion，供 Pipeline(['features', feat], ['clf', ...]) 使用。
    之後要新增字元級/規則級特徵，請 append 到 blocks。
    """
    blocks = [
        ("w_tfidf", _tfidf_block(ngram=(1,2), analyzer="word")),
        # 範例：字元 ngram；需要時解除註解
        # ("c_tfidf", _tfidf_block(ngram=(3,5), analyzer="char", min_df=3, max_df=0.95)),
    ]
    return FeatureUnion(blocks)

def feature_schema_from_fitted(feat_union) -> dict:
    """從已 fit 的 FeatureUnion 取出總維度與名稱哈希（名稱列表可能很大，取 sha256_head 即可）。"""
    names: list[str] = []
    for name, pipe in feat_union.transformer_list:
        # 取對應向量器名稱
        try:
            vec = pipe.named_steps["tfidf"]
            names.extend(list(getattr(vec, "get_feature_names_out")()))
        except Exception:
            # 取不到視為未知塊，但仍可計數
            pass
    joined = "\n".join(names).encode("utf-8", "ignore")
    sha = hashlib.sha256(joined).hexdigest() if names else None
    return {
        "version": "intent-feat-v1",
        "count": int(getattr(feat_union, "n_features_in_", 0)) or None,
        "names_count": len(names),
        "sha256_head": sha,
    }
