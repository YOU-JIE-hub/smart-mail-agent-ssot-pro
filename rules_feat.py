# -*- coding: utf-8 -*-
try:
    from vendor.rules_features import *  # noqa
    __SMA_RULES_FEAT_BACKEND__ = "vendor.rules_features"
except Exception:
    __SMA_RULES_FEAT_BACKEND__ = "shim_fallback"
    class RulesFeaturizer:
        def __init__(self, *_, **__): pass
        def fit(self, X, y=None): return self
        def transform(self, X): return [[0.0] for _ in (X or [])]
    def make_features(text): return [0.0]
    VERSION = "shim-compat"
