"""Explicit real account smoke test, executed by the running orchestrator."""
import json
import time
import urllib.request
import uuid
from pathlib import Path
BASE='http://127.0.0.1:8787/api/'
def call(path,body=None,key=None):
    headers={'Content-Type':'application/json'}
    if key:headers['Idempotency-Key']=key
    req=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
if __name__=='__main__':
    check=call('providers/web-tess/check',{})
    if not check.get('session_ready') or not check.get('controls_mapped'):raise SystemExit(json.dumps(check,ensure_ascii=False))
    task=call('tasks',{'objective':'Teste de conexão autenticada: responda exatamente TESS_AUTH_OK. Não use ferramentas, conectores, busca, arquivos nem ações externas.','project_id':'local','provider':'web-tess','workflow':'direct','spec':{'expected_output':'TESS_AUTH_OK'}},str(uuid.uuid4()))
    print('Tarefa real criada:',task['id'],flush=True)
    deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        state=call('state');current=next(t for t in state['tasks'] if t['id']==task['id'])
        if current['status'] not in ('queued','running'):
            evidence={k:current.get(k) for k in ('id','provider','status','result','error','validation','created_at','updated_at')}
            evidence['mode']='real Tess account browser session; submitted by orchestrator; no API key'
            Path('evidence/tess-auth-real.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
            print(json.dumps(evidence,ensure_ascii=False),flush=True)
            raise SystemExit(0 if current['status']=='completed' else 1)
        time.sleep(2)
    raise SystemExit('A tarefa continua no orquestrador; confira antes de reenviar.')
