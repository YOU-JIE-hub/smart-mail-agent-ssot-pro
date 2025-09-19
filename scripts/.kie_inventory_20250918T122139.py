import os, json, hashlib, mimetypes, time
from pathlib import Path
ROOT = Path(os.environ.get('KIE_DIR','')).expanduser()
TS = os.environ.get('TS','20250918T122139')
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
                try:
                    obj=json.loads(line.strip())
                    if isinstance(obj, dict): samples.append({'keys': sorted(list(obj.keys()))})
                    else: samples.append({'type': type(obj).__name__})
                except Exception:
                    samples.append({'parse':'error'})
    return {'lines': n, 'peek': samples}

def json_info(p):
    try:
        obj=json.loads(Path(p).read_text('utf-8',errors='ignore'))
        if isinstance(obj, dict):
            return {'type':'dict','keys': sorted(list(obj.keys()))[:50]}
        if isinstance(obj, list):
            peek=obj[:3]; kset=sorted(list({k for x in peek if isinstance(x,dict) for k in x.keys()}))
            return {'type':'list','len': len(obj), 'peek_keys': kset}
        return {'type': type(obj).__name__}
    except Exception as e:
        return {'error': str(e)[:200]}

def kind_by_name(p: Path):
    s=p.name.lower()
    if s.endswith('.safetensors'): return 'weights.safetensors'
    if s in ('config.json','tokenizer.json','tokenizer_config.json','special_tokens_map.json'): return 'tokenizer/config'
    if s.endswith('.bpe') or s.endswith('.spm') or s.endswith('.model'): return 'tokenizer/vocab'
    if s.endswith('.jsonl'): return 'data.jsonl'
    if s.endswith('.json'): return 'data.json'
    if s.endswith('.txt'): return 'text'
    if s.endswith('.py'): return 'python'
    if s.endswith('.bin') or s.endswith('.pt'): return 'weights.bin/pt'
    return 'other'

assert ROOT.is_dir(), f'KIE_DIR not found: {ROOT}'
items=[]
for dp, dn, fn in os.walk(ROOT):
    dp=Path(dp)
    for name in sorted(fn):
        p=dp/name
        st=p.stat()
        item={'rel': str(p.relative_to(ROOT)), 'abs': str(p), 'size': st.st_size, 'mtime': time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(st.st_mtime)), 'ext': p.suffix.lower(), 'mime': mimetypes.guess_type(str(p))[0], 'kind': kind_by_name(p)}
        # 輕量指紋（前 4MB）
        try: item['sha256_head']= sha256_head(p)
        except Exception as e: item['sha256_head_error']= str(e)[:120]
        # 額外解析
        try:
            if item['kind']=='data.json': item['json_info']= json_info(p)
            elif item['kind']=='data.jsonl': item['jsonl_info']= jsonl_info(p)
        except Exception as e:
            item['parse_error']= str(e)[:200]
        items.append(item)

out={'ts': TS, 'root': str(ROOT), 'count': len(items), 'items': items}
manifest.write_text(json.dumps(out,ensure_ascii=False,indent=2),'utf-8')
filelist.write_text('\n'.join(i['abs'] for i in items),'utf-8')

# Markdown 摘要
lines=[f'# KIE Inventory @ {TS}', f'- root: ', f'- files: {len(items)}', '']
def fmt(sz):
    units=['B','KB','MB','GB']; i=0
    while sz>=1024 and i<len(units)-1: sz/=1024; i+=1
    return f'{sz:.1f}{units[i]}'
for it in items[:200]:  # 只列前 200 筆明細，避免太長
    lines.append(f"-   | kind={it.get('kind')} | size={fmt(it['size'])} | sha256_head={it.get('sha256_head','-')[:16]}")
md.write_text('\n'.join(lines),'utf-8')
print('[OK] wrote', manifest, 'and', md, 'and', filelist)
