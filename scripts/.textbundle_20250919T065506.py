import os, sys, json, time, hashlib, platform
from pathlib import Path

root = Path.cwd()
OUTDIR = Path(os.environ.get('OUTDIR'))
TOC = Path(os.environ.get('TOC'))
BIG = Path(os.environ.get('BIG'))
INDEX = Path(os.environ.get('INDEX'))
TREE = Path(os.environ.get('TREE'))
BASENAME = os.environ.get('BASENAME')
VOL_BYTES = int(os.environ.get('VOL_BYTES','104857600'))

exc_dirs = {'.git','.venv','venv','node_modules','__pycache__','.cache','dist','build','release_staging','reports_auto/logs'}
# 純文字代碼副檔名（完整收錄）
text_ext = {'.py','.ipynb','.sh','.bash','.ps1','.bat','.cmd','.yaml','.yml','.toml','.ini','.cfg','.mk','.make','.json','.txt','.md','.rst','.sql','.env','.dockerfile','.service','.conf','.pyi','.c','.cc','.cpp','.h','.hpp','.java','.kt','.tsx','.ts','.jsx','.js','.vue','Makefile'}
# 大檔/權重/資料（不收內容，只列出名稱與路徑）
bin_like_ext = {'.pt','.bin','.safetensors','.pkl','.joblib','.zip','.tar','.gz','.xz','.bz2','.7z','.parquet','.feather','.npy','.npz','.onnx','.h5','.pb','.ckpt'}

def is_text_code(p: Path):
    if p.name == 'Makefile': return True
    suff = p.suffix.lower()
    return (suff in text_ext)

def should_list_only(p: Path):
    suff = p.suffix.lower()
    if suff in bin_like_ext: return True
    # 明確資料/模型資料夾也列名：models, weights, datasets, data (但保留 data 下的 .json/.jsonl/.txt/.md 會被上面 text_ext 收到)
    parts = set(p.parts)
    if 'models' in parts or 'weights' in parts or 'datasets' in parts:
        return True
    return False

# 蒐集檔案
files=[]; big_assets=[]
for p in root.rglob('*'):
    if any(part in exc_dirs for part in p.parts):
        continue
    if not p.is_file(): continue
    # 二進位或大檔只列名
    if should_list_only(p) and not is_text_code(p):
        try: sz = p.stat().st_size
        except: sz = None
        big_assets.append({'path': str(p.relative_to(root)), 'size': sz, 'suffix': p.suffix.lower()})
        continue
    # 純文字代碼收錄
    if is_text_code(p):
        files.append(p)

# 優先順序：關鍵檔案在前，方便我先讀
prio = ['tools/api_server.py','tools/pipeline_baseline.py','overrides/tools/pipeline_baseline.py','vendor/rules_features.py','scripts/eval_intent.py','scripts/eval_spam.py','scripts/eval_kie.py','scripts/env.default','Makefile']
def rank(path: Path):
    rel = str(path.relative_to(root)).replace('\\','/')
    for i,k in enumerate(prio):
        if rel==k or rel.startswith(k.rstrip('/')+'/'): return (0,i,rel.lower())
    return (1,9999,rel.lower())
files = sorted(files, key=rank)

# 生成索引、專案樹
INDEX.write_text(json.dumps({'root': str(root), 'count': len(files), 'files':[str(p.relative_to(root)).replace('\\','/') for p in files]}, ensure_ascii=False, indent=2), 'utf-8')
all_paths = []
for p in root.rglob('*'):
    if any(part in exc_dirs for part in p.parts): continue
    if p.is_dir(): continue
    all_paths.append(str(p.relative_to(root)).replace('\\','/'))
TREE.write_text('\n'.join(sorted(all_paths)), 'utf-8')
BIG.write_text(json.dumps({'root': str(root), 'assets': big_assets}, ensure_ascii=False, indent=2), 'utf-8')

# 分卷寫入：每卷 <= VOL_BYTES；文件不截斷，只跨卷續寫
def sha256_file(path: Path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20), b''):
            h.update(chunk)
    return h.hexdigest()

vol=1; written=0; toc={'generated_at': time.strftime('%F %T'), 'root': str(root), 'vol_bytes': VOL_BYTES, 'parts': [], 'files': []}
w=None; outpath=None

def open_new_vol():
    global vol, written, w, outpath
    if w: w.flush(); w.close(); toc['parts'][-1]['sha256']=sha256_file(outpath)
    outpath = OUTDIR / f"{BASENAME}{vol:03d}.txt"
    w = outpath.open('w', encoding='utf-8', newline='\n')
    header = {'note':'Single-file text bundle (multi-volume)','cwd':str(root),'ts':time.strftime('%Y%m%dT%H%M%S'),'limit_bytes':VOL_BYTES,'volume':vol}
    w.write('===== BUNDLE_HEADER =====\n'+json.dumps(header, ensure_ascii=False, indent=2)+'\n')
    written = outpath.stat().st_size
    toc['parts'].append({'part': vol, 'path': outpath.name, 'bytes': None, 'sha256': None})

def marker(rel, tag):
    return f"\n===== {tag} {rel} =====\n"

open_new_vol()
for p in files:
    rel = str(p.relative_to(root)).replace('\\','/')
    try:
        data = p.read_text('utf-8', errors='replace')
    except Exception:
        continue
    block = marker(rel,'BEGIN') + data + '\n' + marker(rel,'END')
    b = block.encode('utf-8')
    # 若當前卷放不下，開新卷
    if written + len(b) > VOL_BYTES:
        # 收尾當前卷
        part_idx = len(toc['parts'])-1
        toc['parts'][part_idx]['bytes'] = written
        open_new_vol()
    w.write(block)
    written += len(b)
    toc['files'].append({'path': rel, 'bytes': len(b), 'volume': vol})

# 收尾最後一卷
part_idx = len(toc['parts'])-1
toc['parts'][part_idx]['bytes'] = written
if w: w.flush(); w.close(); toc['parts'][part_idx]['sha256']=sha256_file(outpath)
TOC.write_text(json.dumps(toc, ensure_ascii=False, indent=2), 'utf-8')
print(json.dumps({'parts': toc['parts'], 'files_count': len(toc['files']), 'big_assets': len(big_assets)}, ensure_ascii=False))
