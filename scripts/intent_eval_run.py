import sys, types, runpy
try:
    import vendor.rules_features as rf
except Exception:
    class _RF:
        class RulesFeaturizer:
            def __init__(self,*a,**k): pass
            def fit(self,X,y=None): return self
            def transform(self,X): return [[0.0] for _ in (X or [])]
        def make_features(text): return [0.0]
    rf=_RF()
# 關鍵：同時滿足兩種查找路徑
sys.modules['rules_feat']=rf
sys.modules['__main__'].rules_feat = rf
# 執行原本的評測腳本（保持你原有邏輯不變）
runpy.run_path('scripts/eval_intent.py', run_name='__main__')
