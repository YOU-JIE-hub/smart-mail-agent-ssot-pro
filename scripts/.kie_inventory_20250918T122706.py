import os, json, hashlib, mimetypes, time
from pathlib import Path
ROOT = Path(os.environ['BUNDLE_DIR'])
TS = os.environ.get('TS','20250918T122706')
status = Path('reports_auto/status'); status.mkdir(parents=True, exist_ok=True)
manifest = status / f'KIE_INVENTORY_{TS}.json'
md = status / f'KIE_INVENTORY_{TS}.md'
filelist = status / f'KIE_FILELIST_{TS}.txt'
def sha256_head(p, cap=4*1024*1024):
  h=hashlib.sha256(); r=0
  with open(p,'rb') as f:
    while True:
      b=f.read(1024*1024)
      if not b: break
      h.update(b); r+=len(b)
      if r>=cap: h.update(b'__TRUNCATED__'); break
  return h.hexdigest()
def jsonl_info(p, max_peek=3):
  n=0; samples=[]
  with open(p,'r',encoding='utf-8',errors='ignore') as f:
    for line in f:
      n+=1
      if len(samples)<max_peek:
        try: obj=json.loads(line.strip()); samples.append({'keys':sorted(obj.keys()) if isinstance(obj,dict) else type(obj).__name__})
        except: samples.append({'parse':'error'})
  return {'lines':n,'peek':samples}
def json_info(p):
  try:
    obj=json.loads(Path(p).read_text('utf-8',errors='ignore'))
    if isinstance(obj, dict): return {'type':'dict','keys':sorted(list(obj.keys()))[:50]}
    if isinstance(obj, list): return {'type':'list','len':len(obj),'peek_keys':sorted(list({k for x in obj[:3] if isinstance(x,dict) for k in x.keys()}))}
    return {'type':type(obj).__name__}
  except Exception as e: return {'error':str(e)[:200]}
def kind(p):
  s=p.name.lower()
  if s.endswith('.safetensors'): return 'weights.safetensors'
  if s in ('config.json','tokenizer.json','tokenizer_config.json','special_tokens_map.json'): return 'tokenizer/config'
  if s.endswith(('.bpe','.spm')) or s=='sentencepiece.bpe.model' or s=='spiece.model' or s=='vocab.json': return 'tokenizer/vocab'
  if s.endswith('.jsonl'): return 'data.jsonl'
  if s.endswith('.json'): return 'data.json'
  if s.endswith('.py'): return 'python'
  return 'other'
assert ROOT.is_dir(), f'Missing bundle: {ROOT}'
items=[]
for dp,_,fn in os.walk(ROOT):
  dp=Path(dp)
  for n in sorted(fn):
    p=dp/n; st=p.stat()
    it={'rel':str(p.relative_to(ROOT)),'abs':str(p),'size':st.st_size,'mtime':time.strftime('%Y-%m-%dT%H:%M:%S',time.localtime(st.st_mtime)),'kind':kind(p)}
    try: it['sha256_head']=sha256_head(p)
    except Exception as e: it['sha256_head_error']=str(e)[:120]
    try:
      if it['kind']=='data.json': it['json_info']=json_info(p)
      elif it['kind']=='data.jsonl': it['jsonl_info']=jsonl_info(p)
    except Exception as e: it['parse_error']=str(e)[:200]
    items.append(it)
out={'ts':TS,'root':str(ROOT),'count':len(items),'items':items}
manifest.write_text(json.dumps(out,ensure_ascii=False,indent=2),'utf-8')
filelist.write_text('\n'.join(i['abs'] for i in items),'utf-8')
lines=[f'# KIE Inventory @ {TS}', f'- root: ', f'- files: {len(items)}','', '## Top (first 200)']
def fmt(sz):
  u=['B','KB','MB','GB']; i=0
  while sz>=1024 and i<len(u)-1: sz/=1024; i+=1
  return f'{sz:.1f}{u[i]}'
for it in items[:200]: lines.append(f"-  | kind={it['kind']} | size={fmt(it['size'])} | sha256_head={it.get('sha256_head','-')[:16]}")
md.write_text('\n'.join(lines),'utf-8')
print('[OK] wrote', manifest, 'and', md)
