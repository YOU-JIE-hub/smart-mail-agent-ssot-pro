# Panic Report
- Exit code: 1
- CMD  : python3 - <<'__PY__'
import os, sys, json, time, re, shutil, hashlib, subprocess as sp
from pathlib import Path

root = Path('.').resolve()
reports = root/'reports_auto'; reports.mkdir(parents=True, exist_ok=True)
hotfix_dir = reports/f'hotfix_backups/{time.strftime('%Y%m%dT%H%M%S')}'; hotfix_dir.mkdir(parents=True, exist_ok=True)

def run(cmd, check=True):
    print('[RUN]', ' '.join(cmd))
    return sp.run(cmd, check=check)

# --- 0) 環境準備：venv 與相依 ---
venv = root/'.venv'
vpy  = venv/'bin/python'
if not venv.exists():
    run(['python3','-m','venv', str(venv)])
run([str(vpy), '-m', 'pip', 'install', '-U', 'pip'])
# requirements.txt 內有就裝，沒有就裝最小集合
req = root/'requirements.txt'
if req.exists():
    run([str(vpy), '-m', 'pip', 'install', '-r', str(req)])
else:
    run([str(vpy), '-m', 'pip', 'install', 'joblib==1.4.2', 'scikit-learn==1.7.1', 'numpy<2.0.0', 'pandas>=2', 'pyyaml>=6'])

# --- 1) 三個模型 ENV（若外部未設，就用你固定值） ---
os.environ.setdefault('INTENT_PKL', str(Path.home()/ 'projects/smart-mail-agent-ssot-pro/models/spam/artifacts/model_pipeline.pkl'))
os.environ.setdefault('SPAM_PKL',   str(Path.home()/ 'projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl'))
os.environ.setdefault('KIE_DIR',    str(Path.home()/ 'projects/smart-mail-agent_ssot/artifacts_inbox/kie1/model'))

# --- 2) Makefile 安全化（train-* 轉為提示占位） ---
mk = root/'Makefile'
if mk.exists():
    bak = hotfix_dir/'Makefile.bak'; shutil.copy2(mk, bak)
    data = mk.read_text(encoding='utf-8', errors='ignore')
    def patch_train_block(text, name):
        pat = rf'(?ms)^\s*{re.escape(name)}:\n(?:\t.*\n)+'
        repl = f"{name}:\n\t@echo \"[INFO] {name} is placeholder. No local train script. Use external pipeline or set ENV to models.\"\n"
        return re.sub(pat, repl, text)
    for tgt in ('train-intent','train-spam','train-kie'):
        data = patch_train_block(data, tgt)
    mk.write_text(data, encoding='utf-8')

# --- 3) 最小測試集（乾淨覆寫） ---
(root/'data/intent_eval').mkdir(parents=True, exist_ok=True)
(root/'data/spam_eval').mkdir(parents=True, exist_ok=True)
(root/'data/intent_eval/test.jsonl').write_text(
    '\n'.join([
        '{text:請提供合約報價與付款方式,label:報價}',
        '{text:APP 登入錯誤，請協助處理,label:技術支援}',
        '{text:我要投訴上次的客服態度,label:投訴}',
        '{text:如何申請退款？流程是什麼,label:規則詢問}',
        '{text:我需要修改聯絡電話與地址,label:資料異動}',
        '{text:你好，想了解一般資訊,label:其他}',
    ]) + '\n', encoding='utf-8'
)
(root/'data/spam_eval/test.jsonl').write_text(
    '\n'.join([
        '{text:Hello team, this is a normal inquiry about pricing.,label:0}',
        '{text:FREE 11859$ CLICK HERE!!! limited offer http://spam,label:1}',
    ]) + '\n', encoding='utf-8'
)

# --- 4) 兼容版總評（直接在此 Python 算完並寫 summary.json ＆ summary.md） ---
sys.path.insert(0, str(root))  # 讓 tools/compat_loader 可被 import
def _default(o):
    try:
        import numpy as np
        if isinstance(o, np.integer): return int(o)
        if isinstance(o, np.floating): return float(o)
        if isinstance(o, np.ndarray): return o.tolist()
    except Exception: pass
    if isinstance(o, set): return list(o)
    return str(o)

def load_jsonl(p):
    p = Path(p)
    if not p.exists(): return [], f'path_missing: {p}'
    rows=[]
    for line in p.read_text(encoding='utf-8', errors='replace').splitlines():
        line=line.strip()
        if not line: continue
        try: rows.append(json.loads(line))
        except Exception as e: return [], f'bad_jsonl: {p} -> {e}'
    return rows, None

def eval_clf(task, env_name, data_path):
    import joblib
    try:
        import tools.compat_loader  # noqa
    except Exception:
        pass
    out={'task':task, 'model_env':env_name, 'model_path':os.environ.get(env_name), 'data_path':str(data_path)}
    mp = os.environ.get(env_name)
    if not mp:
        out.update(status='error', error=f'{env_name}_missing'); return out
    mp = Path(mp).expanduser().resolve()
    if not mp.exists():
        out.update(status='error', error=f'model_not_found: {mp}'); return out
    try:
        clf = joblib.load(mp)
    except Exception as e:
        out.update(status='error', error=f'joblib_load_failed: {e}'); return out
    rows, err = load_jsonl(data_path)
    if err:
        out.update(status='error', error=err); return out
    X = [r.get('text','') for r in rows]
    y_true = [r.get('label') for r in rows] if rows and 'label' in rows[0] else None
    try:
        y_pred = clf.predict(X)
    except Exception as e:
        out.update(status='error', error=f'predict_failed: {e}', n=len(X)); return out
    out.update(status='ok', n=len(X), classes_=list(getattr(clf,'classes_',[])))
    if y_true is not None and all(v is not None for v in y_true):
        from sklearn.metrics import classification_report, accuracy_score
        rep = classification_report(y_true, y_pred, zero_division=0, output_dict=True)
        out['metrics'] = {
            'accuracy': float(accuracy_score(y_true, y_pred)),
            'macro_f1': float(rep.get('macro avg',{}).get('f1-score',0.0)),
            'per_class': {str(k): v for k,v in rep.items() if k not in ('accuracy','macro avg','weighted avg')}
        }
    else:
        out['sample_pred'] = [ (x if isinstance(x,(str,int,float)) else str(x)) for x in y_pred[:10] ]
    return out

def check_kie():
    d = os.environ.get('KIE_DIR')
    out={'task':'kie','dir_env':'KIE_DIR','dir':d}
    if not d: out.update(status='error', error='KIE_DIR_missing'); return out
    p = Path(d).expanduser().resolve()
    if not p.exists(): out.update(status='error', error=f'kie_dir_not_found: {p}'); return out
    req = ['config.json','model.safetensors','tokenizer.json']
    exist = {f: (p/f).exists() for f in req}
    out.update(status='ok' if all(exist.values()) else 'warn', files=exist)
    return out

summary = {
    'created_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
    'intent': eval_clf('intent','INTENT_PKL', root/'data/intent_eval/test.jsonl'),
    'spam':   eval_clf('spam','SPAM_PKL',   root/'data/spam_eval/test.jsonl'),
    'kie':    check_kie(),
}
(reports/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=_default), 'utf-8')

# --- 5) 兩個模型的 PROVENANCE.json ---
def provenance_of(pkl_path):
    import joblib
    try:
        import tools.compat_loader  # noqa
    except Exception:
        pass
    p = Path(pkl_path).expanduser().resolve()
    d = {'path': str(p), 'exists': p.exists(), 'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S')}
    if not p.exists(): return d
    b = p.read_bytes()
    d.update({'size_bytes': int(len(b)), 'sha256': hashlib.sha256(b).hexdigest()})
    try:
        m = joblib.load(p)
        d['classes_'] = list(getattr(m,'classes_', []))
        d['sklearn_pipeline'] = type(m).__name__
    except Exception as e:
        d['load_error'] = str(e)
    (p.parent/'PROVENANCE.json').write_text(json.dumps(d, ensure_ascii=False, indent=2, default=_default), 'utf-8')
    return d

prov={}
if os.environ.get('INTENT_PKL'): prov['intent']=provenance_of(os.environ['INTENT_PKL'])
if os.environ.get('SPAM_PKL'):   prov['spam']=provenance_of(os.environ['SPAM_PKL'])
(reports/'provenance_summary.json').write_text(json.dumps(prov, ensure_ascii=False, indent=2, default=_default), 'utf-8')

# --- 6) 煙霧測試（印 classes 與單句預測） ---
try:
    import joblib, tools.compat_loader  # noqa
    mi = joblib.load(os.environ['INTENT_PKL']); ms = joblib.load(os.environ['SPAM_PKL'])
    print('intent classes:', getattr(mi,'classes_',[]))
    print('intent pred   :', mi.predict(['想查一下合約報價與付款方式'])[0])
    print('spam classes  :', getattr(ms,'classes_',[]))
    print('spam pred     :', ms.predict(['FREE 11859$ click here!!!'])[0])
except Exception as e:
    print('[SMOKE ERROR]', e)

# --- 7) 熱修 scripts/eval_all.py 支援 DATA_*（若 pattern 存在才改，否則跳過） ---
eva = root/'scripts/eval_all.py'
if eva.exists():
    eva_bak = hotfix_dir/'eval_all.py.bak'; shutil.copy2(eva, eva_bak)
    s = eva.read_text(encoding='utf-8', errors='ignore')
    if 'import os' not in s:
        s = s.replace('import sys', 'import sys\nimport os')
    def patch(s, script, env):
        pat = re.compile(rf'run\(\[sys\.executable,\s*"{re.escape(script)}"\]\)')
        repl = (f'run((lambda _d: ([sys.executable, "{script}", "--cfg", "configs/model_paths.yaml"] '
                f'+ ([] if not _d else ["--data", _d])))(os.environ.get("{env}", "")))')
        return pat.sub(repl, s)
    new = patch(s,'scripts/eval_intent.py','DATA_INTENT')
    new = patch(new,'scripts/eval_spam.py','DATA_SPAM')
    new = patch(new,'scripts/eval_kie.py','DATA_KIE')
    eva.write_text(new, encoding='utf-8')

# --- 8) 產生 Markdown 報表（summary.md） ---
j = json.loads((reports/'summary.json').read_text('utf-8'))
lines=[]
lines.append(f"# Smart Mail Agent — 煙霧測試摘要（{j['created_at']}）\n")
def sec(model):
    m=j[model]; lines.append(f"## {model.upper()}\n")
    if m.get('status')!='ok':
        lines.append(f"- 狀態：{m.get('status')}  \n- 錯誤：{m.get('error')}\n"); return
    if model!='kie':
        lines.append(f"- 範例數：{m['n']}  \n- 模型：  \n- classes：{m['classes_']}\n")
        met=m.get('metrics',{})
        if met: lines.append(f"- 準確率：{met.get('accuracy'):.3f}  \n- Macro-F1：{met.get('macro_f1'):.3f}\n")
    else:
        files=m.get('files',{}); ok=m.get('status')
        lines.append(f"- 目錄：  \n- 狀態：{ok}  \n- 必要檔：{files}\n")
(out_dir := (reports/'eval')).mkdir(parents=True, exist_ok=True)
(out_dir/'summary.md').write_text('\n'.join(lines), encoding='utf-8')

# --- 9) README 附上「如何重現」段落（若無則建立最小 README） ---
rd = root/'README.md'
if not rd.exists():
    rd.write_text('# Smart Mail Agent — Minimal Ops README\n\n', encoding='utf-8')
tail = f"\n\n## 煙霧測試報表（如何重現）\n\n"
rd.write_text(rd.read_text(encoding='utf-8') + tail, encoding='utf-8')

print('[DONE] summary.json:', reports/'summary.json')
print('[DONE] summary.md  :', out_dir/'summary.md')
__PY__
- LOG  : reports_auto/panic_20250921T122045/run.log
- ERR  : reports_auto/panic_20250921T122045/run.err
- PY   : reports_auto/panic_20250921T122045/python_stderr.txt
- OOM  : reports_auto/panic_20250921T122045/oom.txt
- TRACE: reports_auto/panic_20250921T122045/xtrace.sh
- SYS  : reports_auto/panic_20250921T122045/system.txt

## Heuristics
