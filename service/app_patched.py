# -*- coding: utf-8 -*-
from service.app import app as _base_app
from service._predict_body_mw import StripPredictExtras

# Wrap original FastAPI app with ASGI middleware
app = StripPredictExtras(_base_app)
