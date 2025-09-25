import re, unicodedata

_URL_RE = re.compile(r'(https?://\S+|www\.\S+)', re.IGNORECASE)

import os

def _intent_url_policy():
    # drop: 移除 URL；token: 以 <URL> 代換
    return os.getenv('INTENT_URL_POLICY', 'drop').lower()

def _strip_urls(s):
    return _URL_RE.sub(' ', s)

def _tokenize_urls(s):
    return _URL_RE.sub(' <URL> ', s)


def _url_tokenize(s, token='<URL>'):
    return _URL_RE.sub(f' {token} ', s)

def _url_strip(s):
    return _URL_RE.sub(' ', s)

def normalize_text(s: str, task: str = 'generic'):
    if not isinstance(s, str):
        s = str(s)
    s = unicodedata.normalize('NFKC', s)
    if task == 'intent':
        s = _url_strip(s)        # ← intent：移除 URL
    else:
        s = (_strip_urls(s) if (task=='intent' and _intent_url_policy() in ('drop','remove','strip')) else _tokenize_urls(s))     # ← spam/其他：<URL>
    s = s.lower()
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def normalize_text(s: str, task: str = 'generic'):
    if not isinstance(s, str):
        s = str(s)
    s = unicodedata.normalize('NFKC', s)

    # 任務感知的 URL 策略 + 大小寫順序
    if task == 'intent':
        # 先移除 URL，再小寫（避免 "<url>" 遺留）
        s = _strip_urls(s)
        s = s.lower()
    elif task == 'spam':
        # 先小寫其他內容，再把 URL 統一替換成 <URL>（大寫保留）
        s = s.lower()
        s = _tokenize_urls(s)
    else:
        # generic：保守作法，tokenize URL 再小寫（token 會被小寫掉）
        s = _tokenize_urls(s)
        s = s.lower()

    # 空白摺疊
    s = re.sub(r'\s+', ' ', s).strip()
    return s
