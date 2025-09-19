import os,json,requests as r, time
base=os.environ.get('SMA_API_BASE','http://127.0.0.1:8088')
def dump(name,obj): open(f'reports_auto/status/{name}','w',encoding='utf-8').write(json.dumps(obj,ensure_ascii=False,indent=2))
m=r.get(f'{base}/debug/model_meta',timeout=5).json(); dump('SMOKE_META.json',m)
c=r.post(f'{base}/classify',json={'text':'Need a quote for 5 units','route':'rule'},timeout=5).json(); dump('SMOKE_CLASSIFY.json',c)
e=r.post(f'{base}/extract',json={'text':'請撥打 02-1234-5678，金額 3000 元'},timeout=5).json(); dump('SMOKE_EXTRACT.json',e)
print('[smoke] ok')
