import os, json, hashlib, sys
from pathlib import Path
from datetime import datetime
ROOT=Path.cwd(); TS=os.getenv('TS','20250918T120540')
STATUS=ROOT/'reports_auto/status'; STATUS.mkdir(parents=True, exist_ok=True)
def sha256(path, cap=4*1024*1024):
  h=hashlib.sha256(); r=0
  with open(path,'rb') as f:
    while True:
      b=f.read(1024*1024)
      if not b: break
      r+=len(b); h.update(b)
      if r>cap: h.update(b'__TRUNCATED__'); break
  return h.hexdigest()

# ---------- 路徑解析（先用環境變數，否則掃描常見位置） ----------
def first_existing(cands):
  for p in cands:
    if p and Path(p).is_file(): return str(Path(p).resolve())
  return None
intent_env=os.getenv('SMA_INTENT_ML_PKL','')
spam_env=os.getenv('SMA_SPAM_ML_PKL','')
kie_env=os.getenv('SMA_KIE_TENSORS','')
intent_path=first_existing([
  intent_env,
  'intent/intent/artifacts/intent_pro_cal.pkl',
  'artifacts/intent_pro_cal.pkl',
  'data/staged_project/artifacts/intent_pro_cal.pkl'
])
spam_path=first_existing([
  spam_env,
  'data/staged_project/artifacts_prod/model_pipeline.pkl',
  'artifacts/model_pipeline.pkl',
  'smart-mail-agent_ssot/artifacts_inbox/77/77/artifacts_sa/spam_rules_lr.pkl'
])
kie_path=first_existing([
  kie_env,
  'kie/kie/model.safetensors',
  'artifacts_kie/model/model.safetensors',
  'smart-mail-agent_ssot/artifacts_inbox/kie1/model.safetensors'
])

report={'ts':TS,'root':str(ROOT),'artifacts':{},'checks':[],'notes':[]}
def add_artifact(task, path):
  p=Path(path); report['artifacts'][task]={'path':str(p), 'exists':p.is_file()}
  if p.is_file():
    report['artifacts'][task].update({'size':p.stat().st_size,'sha256':sha256(p)})

# ---------- Intent：嘗試載入 + 單樣本推論 ----------
def try_intent(path):
  from importlib.metadata import version
  import joblib
  model=joblib.load(path)
  xs=['need a quote for 5 units','請問報價','hello world']
  y=model.predict(xs)
  proba=None
  try:
    proba=model.predict_proba(xs).max(axis=1).tolist()
  except Exception:
    proba=['(n/a)']*len(xs)
  return {'sklearn':version('scikit-learn'),'joblib':version('joblib'),'samples':xs,'pred':list(map(str,y)),'proba':proba}

# ---------- Spam：嘗試載入 + 單樣本推論 ----------
def try_spam(path):
  from importlib.metadata import version
  import joblib
  model=joblib.load(path)
  y=model.predict(xs)
  proba=None
  try:
    proba=model.predict_proba(xs).max(axis=1).tolist()
  except Exception:
    proba=['(n/a)']*len(xs)
  return {'sklearn':version('scikit-learn'),'joblib':version('joblib'),'samples':xs,'pred':list(map(str,y)),'proba':proba}

# ---------- KIE：僅驗資產與設定（不下載、不裝重依賴） ----------
def try_kie(path):
  p=Path(path); d=p.parent
  cfg=None
  for name in ['config.json','tokenizer_config.json','tokenizer.json','sentencepiece.bpe.model']:
    if (d/name).exists(): cfg=name; break
  return {'weights_exists':p.is_file(),'neighbor_cfg':cfg or '(missing)'}

# ---------- 執行 ----------
if intent_path: add_artifact('intent', intent_path)
if spam_path:   add_artifact('spam',   spam_path)
if kie_path:    add_artifact('kie',    kie_path)

try:
  if intent_path: report['intent']=try_intent(intent_path); report['checks'].append('intent:ok')
  else: report['notes'].append('intent artifact not found'); report['checks'].append('intent:missing')
except Exception as e:
  report['intent']={'error':str(e)}; report['checks'].append('intent:fail')

try:
  if spam_path: report['spam']=try_spam(spam_path); report['checks'].append('spam:ok')
  else: report['notes'].append('spam artifact not found'); report['checks'].append('spam:missing')
except Exception as e:
  report['spam']={'error':str(e)}; report['checks'].append('spam:fail')

try:
  if kie_path: report['kie']=try_kie(kie_path); report['checks'].append('kie:asset_checked')
  else: report['notes'].append('kie weights not found'); report['checks'].append('kie:missing')
except Exception as e:
  report['kie']={'error':str(e)}; report['checks'].append('kie:fail')

# ---------- 輸出 ----------
json_path=STATUS/f'TRI_PROVE_{TS}.json'; md_path=STATUS/f'TRI_PROVE_{TS}.md'
json_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
def md(): 
  lines=[f'# TRI PROVE @ {TS}', f'- root: {report["root"]}', '']
  for t in ['intent','spam','kie']:
    lines.append(f'## {t.upper()}')
    art=report['artifacts'].get(t)
    if art: lines.append(f'- path: \n- size: {art.get("size")}\n- sha256: ')
    info=report.get(t, {})
    if 'error' in info: lines.append(f'- ERROR: ')
    else:
      for k,v in info.items(): lines.append(f'- {k}: {v}')
    lines.append('')
  lines.append('## Checks\n- ' + '\n- '.join(report['checks']))
  if report['notes']: lines.append('\n## Notes\n- ' + '\n- '.join(report['notes']))
  return '\n'.join(lines)
md_path.write_text(md(),'utf-8')
print('[OK] wrote', json_path, 'and', md_path)
