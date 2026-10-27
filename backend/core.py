"""Durable local supervisor. Provider credentials never enter application storage."""
import json
import logging
import os
import signal
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone
from backend.web_providers import WebAdapter, DEFAULT_TESS, validate as validate_provider
from backend.policy import choose, build_context, validate_output
from backend.integrations import GeminiAdapter, ReaAdapter, AntigravityAdapter, REA_STAGES
from backend.decision import Decision


def load_env():
    env_file = Path(__file__).resolve().parent.parent / '.env'
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))
    extra_paths = ['/opt/homebrew/bin', '/usr/local/bin']
    nvm_dir = Path.home() / '.nvm' / 'versions' / 'node'
    if nvm_dir.is_dir():
        for p in nvm_dir.glob('*/bin'):
            if p.is_dir():
                extra_paths.append(str(p))
    cur_path = os.environ.get('PATH', '')
    for ep in extra_paths:
        if ep not in cur_path and Path(ep).is_dir():
            cur_path = f"{ep}:{cur_path}"
    os.environ['PATH'] = cur_path


load_env()


def now():
    return datetime.now(timezone.utc).isoformat()


def classify_error(event):
    # Only explicit structured codes or authoritative usage limits permit specialized handling.
    if not isinstance(event, dict):
        return 'failed'
    code = event.get('code', '')
    if code in ('rate_limit_exceeded', 'usage_limit_reached'):
        return 'rate_limited'
    if code in ('authentication_required', 'invalid_api_key', 'unauthorized'):
        return 'authentication_required'
    msg = (event.get('message', '') or event.get('text', '')).strip().casefold()
    if any(k in msg for k in ("you've hit your usage limit", "usage limit reached", "rate limit exceeded", "quota exceeded")):
        return 'rate_limited'
    return 'failed'


def handoff(task):
    return {'version': 1, 'task_id': task['id'], 'objective': task['objective'],
            'constraints': ['Somente leitura. Não alterar arquivos.', 'Não repetir trabalho confirmado.'],
            'state': task['status'], 'confirmed_result': task.get('result', ''),
            'known_error': task.get('error'), 'files': [], 'decisions': [], 'tests': [],
            'next_action': 'Continuar apenas pendências; verificar resultado já confirmado.',
            'provider': task['provider'], 'workflow': task.get('workflow', 'direct'), 'created_at': now()}


class Store:
    def __init__(self, path, root):
        self.path, self.root = str(path), str(Path(root).resolve())
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS api_providers(id TEXT PRIMARY KEY,config TEXT);
            CREATE TABLE IF NOT EXISTS web_providers(id TEXT PRIMARY KEY,config TEXT);
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT,path TEXT);
            CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,project_id TEXT,objective TEXT,provider TEXT,status TEXT,result TEXT DEFAULT '',usage TEXT DEFAULT '{}',error TEXT,created_at TEXT,updated_at TEXT);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT,kind TEXT,payload TEXT,time TEXT);
            CREATE TABLE IF NOT EXISTS checkpoints(id INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT,payload TEXT,time TEXT);
            CREATE TABLE IF NOT EXISTS memory(id TEXT PRIMARY KEY,project_id TEXT,content TEXT,time TEXT);
            CREATE TABLE IF NOT EXISTS commands(key TEXT PRIMARY KEY,task_id TEXT);
            ''')
            db.execute("CREATE TABLE IF NOT EXISTS revisions(task_id TEXT PRIMARY KEY,parent_id TEXT,source_review_id TEXT,base_path TEXT,base_hash TEXT,status TEXT,changes TEXT DEFAULT '{}',validation TEXT DEFAULT '{}',after_review_id TEXT,created_at TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS visual_reviews(task_id TEXT PRIMARY KEY,parent_id TEXT,capture TEXT DEFAULT '{}',report TEXT DEFAULT '',time TEXT)")
            db.execute('CREATE TABLE IF NOT EXISTS artifacts(task_id TEXT PRIMARY KEY, path TEXT, manifest TEXT, time TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS task_steps(task_id TEXT, stage TEXT, output TEXT, time TEXT, PRIMARY KEY(task_id,stage))')
            columns = {r[1] for r in db.execute('PRAGMA table_info(tasks)')}
            for name, default in [('workflow', 'direct'), ('spec', '{}'), ('requested_provider', ''), ('routing', '{}'), ('context_metrics', '{}'), ('validation', '{}'), ('quality', 'unreviewed')]:
                if name not in columns:
                    db.execute("ALTER TABLE tasks ADD COLUMN "+name+" TEXT DEFAULT '"+default+"'")
            memory_columns = {r[1] for r in db.execute('PRAGMA table_info(memory)')}
            if 'kind' not in memory_columns:
                db.execute("ALTER TABLE memory ADD COLUMN kind TEXT DEFAULT 'constraint'")
            db.execute('INSERT OR IGNORE INTO projects VALUES(?,?,?)', ('local', 'AI Orchestrator', self.root))

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def event(self, db, task_id, kind, payload):
        db.execute('INSERT INTO events(task_id,kind,payload,time) VALUES(?,?,?,?)',
                   (task_id, kind, json.dumps(payload, ensure_ascii=False), now()))

    def task(self, id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM tasks WHERE id=?', (id,)).fetchone()
            if not row:
                raise ValueError('Tarefa não encontrada')
            return dict(row)

    def checkpoint(self, db, task):
        p = handoff(task)
        artifact=db.execute('SELECT path,manifest FROM artifacts WHERE task_id=?',(task['id'],)).fetchone()
        if artifact:p['artifact']={'path':artifact['path'],'manifest':json.loads(artifact['manifest'])}
        p['confirmed_stages'] = [dict(r) for r in db.execute('SELECT stage,output,time FROM task_steps WHERE task_id=? ORDER BY time', (task['id'],))]
        db.execute('INSERT INTO checkpoints(task_id,payload,time) VALUES(?,?,?)',
                   (task['id'], json.dumps(p, ensure_ascii=False), now()))
        self.event(db, task['id'], 'checkpoint', {'version': 1, 'state': task['status']})

    def execution_evidence(self, db, task_id):
        changes = []
        commands = []
        for row in db.execute("SELECT id,payload FROM events WHERE task_id=? AND kind='tool_result' ORDER BY id", (task_id,)):
            item = json.loads(row['payload'])
            result = item.get('result') or {}
            name = item.get('name')
            if name in ('write_file', 'edit_file', 'delete_file') and result.get('status') == 'ok':
                changes.append({'path': result.get('path'), 'tool': name, 'event_id': row['id']})
            elif name == 'run_command':
                commands.append({'command': result.get('command'), 'status': result.get('status'),
                                 'exit_code': result.get('exit_code'), 'event_id': row['id']})
        return {'source': 'runtime_tool_results', 'files_changed': changes, 'commands': commands,
                'scope': 'Evidências históricas; inspecione os arquivos para confirmar o estado atual.'}

    def create(self, objective, project, provider, key, workflow="direct", spec=None):
        objective = objective.strip()
        with self.connect() as db:
            known_provider = provider in ('auto', 'codex', 'gemini', 'antigravity', 'rea', 'web-tess', 'tess') or bool(db.execute('SELECT id FROM web_providers WHERE id=?', (provider,)).fetchone())
        if not objective or len(objective) > 20000 or not known_provider:
            raise ValueError('Objetivo inválido ou provedor não habilitado')
        if spec is not None and (not isinstance(spec,dict) or ('expected_output' in spec and (not isinstance(spec['expected_output'],str) or len(spec['expected_output'])>20000))):
            raise ValueError('Critério de saída inválido')
        if workflow not in ('direct', 'rea', 'deliver', 'auto', 'visual_review', 'improve', 'work'):
            raise ValueError('Fluxo inválido')
        if workflow=='auto':
            from backend.policy import category
            words=objective.casefold()
            workflow='work' if any(w in words for w in ('execute ', 'executar ', 'rode ', 'rodar ', 'run tests', 'npm ', 'python3 -m ', 'pytest')) else 'deliver' if any(w in words for w in ('crie ','criar ','desenvolv','implemente','construa','construir','build a','create a')) else 'direct'
        if provider.startswith('web-') and workflow not in ('direct', 'rea', 'work', 'deliver', 'improve'):
            raise ValueError('Sessões e agentes de chat suportam resposta e planejamento REA; selecione esses fluxos.')
        if provider == 'rea' and workflow != 'direct':
            raise ValueError('Motor REA usa análise estática direta')
        if not key or len(key) > 100:
            raise ValueError('Chave idempotente obrigatória')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT task_id FROM commands WHERE key=?', (key,)).fetchone()
            if old:
                return old[0]
            if not db.execute('SELECT id FROM projects WHERE id=?', (project,)).fetchone():
                raise ValueError('Projeto não encontrado')
            spec = dict(spec or {})
            if spec.get('conversation_parent'):
                parent = db.execute('SELECT * FROM tasks WHERE id=? AND project_id=?', (spec['conversation_parent'], project)).fetchone()
                if not parent or parent['status'] in ('running', 'queued'):
                    raise ValueError('A conversa anterior deve estar concluída e pertencer ao mesmo projeto')
                history = json.loads(parent['spec']).get('conversation_history', [])
                history = history + [{'objective': parent['objective'], 'result': parent['result'],
                                      'execution_evidence': self.execution_evidence(db, parent['id'])}]
                cursor = parent
                for turn in reversed(history):
                    if cursor is None:
                        break
                    turn['task_id'] = cursor['id']
                    turn['execution_evidence'] = self.execution_evidence(db, cursor['id'])
                    previous_id = json.loads(cursor['spec']).get('conversation_parent')
                    cursor = db.execute('SELECT * FROM tasks WHERE id=? AND project_id=?',
                                        (previous_id, project)).fetchone() if previous_id else None
                if len(json.dumps(history)) > 40000:
                    raise ValueError('Histórico excede o orçamento; inicie uma nova conversa')
                spec['conversation_history'] = history
            else:
                spec.pop('conversation_history', None)
            id = uuid.uuid4().hex[:12]
            db.execute('INSERT INTO tasks(id,project_id,objective,provider,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
                       (id, project, objective, provider, 'queued', now(), now()))
            db.execute('UPDATE tasks SET workflow=?,spec=?,requested_provider=? WHERE id=?', (workflow, json.dumps(spec or {}), provider, id))
            db.execute('INSERT INTO commands VALUES(?,?)', (key, id))
            self.event(db, id, 'queued', {'reason': 'Roteamento automático na execução; política somente leitura', 'workflow': workflow})
            return id

    def update(self, id, status, **values):
        if set(values) - {'result', 'usage', 'error', 'routing', 'context_metrics', 'validation', 'quality'}:
            raise ValueError('Campo inválido')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM tasks WHERE id=?', (id,)).fetchone()
            if not row:
                raise ValueError('Tarefa não encontrada')
            # Cancellation wins over an in-flight provider completion.
            if row['status'] == 'cancelled' and status != 'queued':
                return
            fields = {'status': status, 'updated_at': now(), **values}
            db.execute('UPDATE tasks SET '+','.join(k+'=?' for k in fields)+' WHERE id=?', (*fields.values(), id))
            task = dict(db.execute('SELECT * FROM tasks WHERE id=?', (id,)).fetchone())
            self.checkpoint(db, task)
            self.event(db, id, status, {'error': values.get('error')})

    def recover(self):
        with self.connect() as db:
            ids = [r[0] for r in db.execute("SELECT id FROM tasks WHERE status IN ('running','queued')")]
        for id in ids:
            self.update(id, 'interrupted', error='Backend reiniciado; retome explicitamente a partir do checkpoint.')

    @staticmethod
    def conversation_roots(tasks):
        by_id = {t['id']: t for t in tasks}
        roots = {}
        for task in tasks:
            current = task
            seen = set()
            while current['id'] not in seen:
                seen.add(current['id'])
                parent = json.loads(current['spec']).get('conversation_parent')
                if parent not in by_id:
                    break
                current = by_id[parent]
            roots[task['id']] = current['id']
        return roots

    def delete_conversation(self, id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            tasks = [dict(r) for r in db.execute('SELECT * FROM tasks')]
            roots = self.conversation_roots(tasks)
            if id not in roots:
                raise ValueError('Conversa não encontrada')
            ids = {key for key, root in roots.items() if root == roots[id]}
            # Include dependent reviews and revisions to avoid dangling task links.
            while True:
                extra = {t['id'] for t in tasks if json.loads(t['spec']).get('parent_id') in ids}
                if extra <= ids:
                    break
                ids |= extra
            if any(t['id'] in ids and t['status'] in ('running', 'queued') for t in tasks):
                raise ValueError('Cancele as execuções ativas antes de excluir a conversa')
            for task_id in ids:
                for table in ('events', 'checkpoints', 'commands', 'task_steps', 'artifacts', 'visual_reviews', 'revisions'):
                    db.execute('DELETE FROM '+table+' WHERE task_id=?', (task_id,))
                db.execute('DELETE FROM tasks WHERE id=?', (task_id,))
            self.event(db, None, 'conversation_deleted', {'conversation_id': roots[id]})
        return {'ok': True, 'deleted_ids': sorted(ids)}

    def snapshot(self):
        with self.connect() as db:
            data = {name: [dict(r) for r in db.execute('SELECT * FROM '+name+order)] for name, order in
                    [('projects', ''), ('tasks', ' ORDER BY created_at DESC'), ('events', ' ORDER BY id DESC LIMIT 500'),
                     ('checkpoints', ' ORDER BY id DESC LIMIT 200'), ('memory', ' ORDER BY time DESC'), ('task_steps', ' ORDER BY time'), ('artifacts', ' ORDER BY time'), ('visual_reviews', ' ORDER BY time DESC'), ('revisions', ' ORDER BY created_at DESC')]}
        roots = self.conversation_roots(data['tasks'])
        for t in data['tasks']:
            t['conversation_id'] = roots[t['id']]
            t['conversation_history'] = json.loads(t['spec']).get('conversation_history', [])
            for field in ('usage','routing','context_metrics','validation'):
                t[field] = json.loads(t[field])
        for revision in data['revisions']:
            for field in ('changes','validation'):revision[field]=json.loads(revision[field])
        for review in data['visual_reviews']:
            review['capture']=json.loads(review['capture'])
            from backend.revisions import suggestions
            review['suggestions']=suggestions(review['report'])
        for artifact in data['artifacts']:
            artifact['manifest']=json.loads(artifact['manifest'])
        for name in ('events', 'checkpoints'):
            for item in data[name]:
                item['payload'] = json.loads(item['payload'])
        return data


class CodexAdapter:
    id = 'codex'
    capabilities = {'read_only': True, 'structured_events': True, 'usage': True, 'write': False, 'automatic_failover': False}

    def probe(self):
        binary = shutil.which('codex')
        if not binary:
            return {'id': self.id, 'installed': False, 'state': 'offline', 'capabilities': self.capabilities}
        try:
            p = subprocess.run([binary, 'login', 'status'], capture_output=True, text=True, timeout=10)
            # Require ChatGPT auth, disallow silent API-key billing.
            auth = p.returncode == 0 and 'using ChatGPT' in (p.stdout+p.stderr)
            return {'id': self.id, 'installed': True, 'state': 'available' if auth else 'authentication_required',
                    'auth': 'ChatGPT' if auth else 'Login ChatGPT necessário', 'capabilities': self.capabilities}
        except (OSError, subprocess.TimeoutExpired):
            return {'id': self.id, 'installed': True, 'state': 'offline', 'capabilities': self.capabilities}

    def execute_improvements(self,prompt,cwd,on_event,cancel,images):
        return self.execute(prompt,cwd,on_event,cancel,timeout=1200,write=True,images=images)

    def execute_visual(self,prompt,cwd,on_event,cancel,images):
        return self.execute(prompt,cwd,on_event,cancel,images=images)

    def execute_build(self,prompt,cwd,on_event,cancel):
        return self.execute(prompt,cwd,on_event,cancel,timeout=1200,write=True)

    def execute(self, prompt, cwd, on_event, cancel, timeout=600,write=False,images=None):
        if self.probe()['state'] != 'available':
            return {'status': 'authentication_required', 'error': 'Execute codex login com sua conta ChatGPT.', 'result': '', 'usage': {}}
        env = dict(os.environ)
        for key in ('OPENAI_API_KEY', 'CODEX_API_KEY'):
            env.pop(key, None)
        args = [shutil.which('codex'), 'exec', '--ephemeral', '--skip-git-repo-check', '--sandbox', 'workspace-write' if write else 'read-only', '--json', '-']
        if images:
            index=args.index('--json')
            image_args=[]
            for image in images:image_args.extend(['--image',str(image)])
            args[index:index]=image_args
        args[1:1] = ['-a', 'never']
        p = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, text=True, start_new_session=(os.name == 'posix'))
        output, usage, failures = [], {}, []
        expired = threading.Event()
        def stop():
            if p.poll() is None:
                try:
                    if os.name == 'posix':
                        os.killpg(p.pid, signal.SIGTERM)
                    else:
                        p.terminate()
                    p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    if os.name == 'posix':
                        os.killpg(p.pid, signal.SIGKILL)
                    else:
                        p.kill()
                except ProcessLookupError:
                    pass
        def guard():
            started = time.monotonic()
            while p.poll() is None:
                if cancel.wait(.1):
                    stop()
                    return
                if time.monotonic()-started > timeout:
                    expired.set()
                    stop()
                    return
        watcher = threading.Thread(target=guard, daemon=True)
        watcher.start()
        try:
            p.stdin.write(prompt)
            p.stdin.close()
            for line in p.stdout:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                kind = e.get('type', 'unknown')
                # Persist useful public outputs, never hidden reasoning/tool payloads.
                if kind == 'item.completed' and e.get('item', {}).get('type') == 'agent_message':
                    text = e['item'].get('text', '')
                    output.append(text)
                    on_event('message', {'text': text})
                elif kind == 'turn.completed':
                    usage = e.get('usage', {})
                    on_event('usage', usage)
                elif kind in ('turn.failed', 'error'):
                    err = e.get('error', e)
                    failures.append(err if isinstance(err, dict) else {'message': str(err)})
                    on_event('provider_error', failures[-1])
            p.wait()
        finally:
            stop()
            p.stdout.close()
            watcher.join(timeout=4)
        status = ('cancelled' if cancel.is_set() else 'interrupted' if expired.is_set() else
                  classify_error(failures[-1]) if failures else 'completed' if p.returncode == 0 and output else 'failed')
        return {'status': status, 'result': '\n\n'.join(output), 'usage': usage,
                'error': None if status == 'completed' else ('Tempo limite' if expired.is_set() else json.dumps(failures[-1], ensure_ascii=False) if failures else 'Execução encerrada sem resultado completo')}


class Supervisor:
    def __init__(self, store, adapter=None):
        self.store = store
        self.adapter = adapter or CodexAdapter()
        self.adapters = {'codex': self.adapter, 'gemini': GeminiAdapter(), 'rea': ReaAdapter(), 'antigravity': AntigravityAdapter()}
        self.lock, self.signals = threading.Lock(), {}
        self.active = None
        self.adapters['web-tess'] = WebAdapter(DEFAULT_TESS)
        from backend.web_providers import DEFAULT_CHATGPT
        self.adapters['web-chatgpt'] = WebAdapter(DEFAULT_CHATGPT)
        if os.environ.get('TESS_API_KEY'):
            from backend.api_providers import ApiAdapter, DEFAULT_TESS_API
            self.adapters['tess'] = ApiAdapter(DEFAULT_TESS_API)
        with store.connect() as db:
            for row in db.execute("SELECT config FROM web_providers"):
                adapter = WebAdapter(json.loads(row[0]))
                self.adapters[adapter.id] = adapter

    def save_provider(self, config):
        config = validate_provider(config)
        with self.lock:
            if self.active:
                raise ValueError("Aguarde a tarefa ativa antes de alterar conexões.")
            with self.store.connect() as db:
                if db.execute("SELECT id FROM tasks WHERE provider=? AND status='queued'", (config["id"],)).fetchone():
                    raise ValueError("Conexão em uso por tarefa na fila.")
                db.execute("INSERT INTO web_providers VALUES(?,?) ON CONFLICT(id) DO UPDATE SET config=excluded.config", (config["id"], json.dumps(config)))
            existing = self.adapters.get(config['id'])
            if not isinstance(existing, WebAdapter) or existing.config != config:
                self.adapters[config['id']] = WebAdapter(config)
        return {"id": config["id"]}

    def provider_action(self, id, action):
        adapter = self.adapters.get(id)
        from backend.api_providers import ApiAdapter
        if isinstance(adapter, ApiAdapter):
            if action == 'check':
                return adapter.check()
            raise ValueError('Ação inválida para provedor de API.')
        if not isinstance(adapter, WebAdapter):
            if adapter and id in ('codex', 'antigravity', 'gemini') and action == 'check':
                return adapter.check_auth(explicit=True) if isinstance(adapter, AntigravityAdapter) else adapter.probe()
            raise ValueError('Selecione uma conexão válida.')
        if action == 'login':
            return adapter.open_login()
        if action == 'check':
            return adapter.check()
        raise ValueError('Ação de autenticação inválida.')

    def refresh_connections(self):
        if self.active:
            return
        from backend.api_providers import ApiAdapter
        for adapter in list(self.adapters.values()):
            try:
                if isinstance(adapter, WebAdapter):
                    if not adapter.operation.locked():
                        adapter.check()
                elif isinstance(adapter, ApiAdapter):
                    adapter.check()
                elif isinstance(adapter, AntigravityAdapter):
                    adapter.check_auth()
            except Exception:
                # Authentication checks are isolated; no provider output or credential diagnostics logged.
                continue

    def connection_loop(self, stopped):
        while not stopped.is_set():
            self.refresh_connections()
            stopped.wait(15)

    def providers(self):
        providers = [adapter.probe() for adapter in list(self.adapters.values())]
        with self.store.connect() as db:
            for provider in providers:
                latest = db.execute("SELECT status FROM tasks WHERE provider=? AND status NOT IN ('queued','running') ORDER BY created_at DESC LIMIT 1", (provider['id'],)).fetchone()
                provider['automatic_routing_blocked'] = bool(latest and latest['status'] in ('failed', 'rate_limited', 'authentication_required', 'interrupted'))
        if self.active:
            active_provider = self.store.task(self.active)['provider']
            for provider in providers:
                if provider['id'] == active_provider:
                    provider['state'] = 'running'
        return providers

    def cancel(self, id):
        with self.lock:
            task = self.store.task(id)
            if task['status'] not in ('queued', 'running'):
                raise ValueError('Tarefa não está em execução ou fila')
            if id in self.signals:
                self.signals[id].set()
            self.store.update(id, 'cancelled', error='Cancelamento solicitado pelo usuário')

    def resume(self, id):
        with self.lock:
            if self.store.task(id)['status'] not in ('interrupted', 'failed', 'cancelled', 'rate_limited', 'authentication_required', 'blocked', 'needs_review'):
                raise ValueError('Estado não permite retomada')
            if self.active == id:
                raise ValueError('Aguarde encerramento do processo anterior')
            prior=self.store.task(id)
            if (prior['provider']=='antigravity' and prior['workflow']=='rea'
                    and (prior.get('error') or '').startswith('Antigravity encerrou com SUCCESS, mas sem resposta pública')
                    and self.adapter.probe().get('state')=='available'):
                decision={'selected':'codex','reason':'Retomada após ausência comprovada de resposta pública do Gemini; preservar etapas REA confirmadas e evitar repetir a chamada que falhou.'}
                with self.store.connect() as db:
                    db.execute('UPDATE tasks SET provider=?,routing=? WHERE id=?',('codex',json.dumps(decision,ensure_ascii=False),id))
                    self.store.event(db,id,'rea_stage_provider_changed',decision)
            elif prior['status'] == 'rate_limited' or 'usage limit' in (prior.get('error') or '').lower() or 'quota' in (prior.get('error') or '').lower():
                failover = Decision.decide_failover(prior, prior['provider'], prior.get('error') or 'Limite de uso atingido', self.providers())
                if failover:
                    new_provider = failover['selected_provider']
                    with self.store.connect() as db:
                        db.execute('UPDATE tasks SET provider=?,routing=? WHERE id=?', (new_provider, json.dumps(failover, ensure_ascii=False), id))
                        self.store.event(db, id, 'provider_failover', failover)
            self.store.update(id, 'queued', error=None)

    def run_once(self):
        with self.lock:
            if self.active:
                return False
            with self.store.connect() as db:
                row = db.execute("SELECT * FROM tasks WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if not row:
                return False
            task = dict(row)
            id = task['id']
            if task['provider']=='auto':
                candidates=self.providers()
                if task['workflow'] in ('deliver','visual_review', 'improve'):
                    codex_avail = any(p['id']=='codex' and p.get('state')=='available' for p in candidates)
                    if codex_avail:
                        candidates=[p for p in candidates if p['id']=='codex']
                    else:
                        candidates=[p for p in candidates if p['id'] in ('codex', 'antigravity') or p.get('automatic_routing')]
                selected, decision=choose(task, candidates, self.store.snapshot()['tasks'])
                if not selected:
                    self.store.update(id, 'blocked', routing=json.dumps(decision), error=decision['reason'])
                    if task['workflow']=='visual_review':
                        with self.store.connect() as db:db.execute("UPDATE revisions SET status='review_failed' WHERE after_review_id=?",(id,))
                    return True
                with self.store.connect() as db:
                    db.execute('UPDATE tasks SET provider=?,routing=? WHERE id=?',(selected,json.dumps(decision,ensure_ascii=False),id))
                    self.store.event(db,id,'agent_selected',decision)
                task['provider']=selected
            elif task['provider'] != 'rea':
                current = next((p for p in self.providers() if p['id'] == task['provider']), None)
                if not current or not current.get('installed') or current.get('state') != 'available':
                    self.store.update(id, 'blocked', error='Agente selecionado indisponível. Selecione um agente pronto ou use seleção automática.')
                    return True
            self.store.update(id, 'running')
            self.active = id
            cancel = self.signals[id] = threading.Event()
        try:
            with self.store.connect() as db:
                project = db.execute('SELECT * FROM projects WHERE id=?', (task['project_id'],)).fetchone()
            def emit(kind, payload):
                with self.store.connect() as db:
                    self.store.event(db, id, kind, payload)
                    if kind == 'tool_result':
                        self.store.checkpoint(db, self.store.task(id))
                    if kind == 'message':
                        old = db.execute('SELECT result FROM tasks WHERE id=?', (id,)).fetchone()[0]
                        db.execute('UPDATE tasks SET result=?,updated_at=? WHERE id=?', (old+'\n\n'+payload['text'], now(), id))
            with self.store.connect() as db:
                memories = [dict(r) for r in db.execute('SELECT * FROM memory WHERE project_id=? ORDER BY time DESC', (task['project_id'],))]
            prompt, metrics = build_context(task, memories)
            with self.store.connect() as db:
                db.execute('UPDATE tasks SET context_metrics=? WHERE id=?',(json.dumps(metrics,ensure_ascii=False),id))
                self.store.event(db,id,'context_prepared',metrics)
            adapter = self.adapter if task['provider'] == 'codex' else self.adapters.get(task['provider'], self.adapter)
            def execute_readonly(selected_adapter):
                if hasattr(selected_adapter, 'chat_turn') or isinstance(selected_adapter, WebAdapter):
                    from backend.agent_engine import run_universal_agent
                    result = run_universal_agent(selected_adapter, prompt, project['path'], emit, cancel, read_only=True)
                    result.pop('files_mutated', None)
                    return result
                return selected_adapter.execute(prompt, project['path'], emit, cancel)
            if task['workflow']=='work':
                from backend.agent_engine import run_universal_agent
                if not Path(project['path']).is_dir():
                    raise ValueError('Pasta vinculada indisponível')
                result=run_universal_agent(adapter, prompt, project['path'], emit, cancel)
                result.pop('files_mutated', None)
            elif task['workflow']=='improve':
                result=self.run_improvements(task,emit,cancel)
            elif task['workflow']=='visual_review':
                result=self.run_visual_review(task,emit,cancel)
            elif task['provider'] == 'rea':
                result = adapter.execute(json.loads(task['spec']), project['path'], emit, cancel)
            elif task['workflow'] == 'deliver':
                planned=self.run_rea(task,prompt,project['path'],adapter,emit,cancel)
                if planned['status']=='completed':
                    result=self.run_delivery(task,emit,cancel)
                    result['usage']={k:planned['usage'].get(k,0)+result['usage'].get(k,0) for k in set(planned['usage'])|set(result['usage'])}
                else:
                    result=planned
            elif task['workflow'] == 'rea':
                result = self.run_rea(task, prompt, project['path'], adapter, emit, cancel)
            else:
                result = execute_readonly(adapter)
                if result['status'] in ('rate_limited', 'failed') and not cancel.is_set():
                    err_msg = result.get('error') or ''
                    is_quota = result['status'] == 'rate_limited' or any(k in err_msg.lower() for k in ('usage limit', 'rate limit', 'quota'))
                    if is_quota or result['status'] == 'failed':
                        failover = Decision.decide_failover(task, task['provider'], err_msg, self.providers())
                        if failover:
                            alt_provider = failover['selected_provider']
                            emit('provider_failover', {
                                'from_provider': task['provider'],
                                'to_provider': alt_provider,
                                'reason': failover['reason'],
                                'confidence': failover['confidence']
                            })
                            with self.store.connect() as db:
                                db.execute('UPDATE tasks SET provider=?, routing=? WHERE id=?',
                                           (alt_provider, json.dumps(failover, ensure_ascii=False), id))
                                self.store.event(db, id, 'provider_failover', failover)
                            task['provider'] = alt_provider
                            adapter = self.adapters.get(alt_provider, self.adapter)
                            result = execute_readonly(adapter)
            if result['status']=='completed' and task['provider']!='rea' and task['workflow'] not in ('deliver','visual_review', 'improve'):
                validation=validate_output(result['result'],json.loads(task['spec']))
                with self.store.connect() as db:
                    db.execute('UPDATE tasks SET validation=? WHERE id=?',(json.dumps(validation),id))
                    self.store.event(db,id,'result_validation',validation)
                if validation['status']=='failed':
                    result['status']='needs_review'
                    result['error']='Resultado recebido, mas o critério de saída exata falhou. Sem nova chamada automática.'
            previous_usage = json.loads(task['usage'])
            result['usage'] = {k: previous_usage.get(k, 0)+v for k, v in result['usage'].items() if isinstance(v, (int, float))} | {k: v for k, v in previous_usage.items() if k not in result['usage']}
            final_status=result.pop('status')
            self.store.update(id, final_status, **{**result, 'usage': json.dumps(result['usage'])})
            if task['workflow']=='improve' and final_status!='completed':
                with self.store.connect() as db:db.execute("UPDATE revisions SET status=CASE WHEN status='validation_failed' THEN status ELSE ? END WHERE task_id=?",(final_status,id))
            if task['workflow'] in ('deliver','improve') and final_status=='completed' and self.store.task(id)['status']=='completed' and hasattr(self.adapter,'execute_visual'):
                try:
                    review_id=self.request_visual_review(id)
                    if task['workflow']=='improve':
                        with self.store.connect() as db:db.execute("UPDATE revisions SET after_review_id=?,status='reviewing' WHERE task_id=?",(review_id,id))
                except Exception as review_error:
                    emit('visual_review_unavailable',{'reason':str(review_error)})
        except Exception as exc:
            self.store.update(id, 'failed', error=type(exc).__name__+': '+str(exc))
            if task['workflow']=='improve':
                with self.store.connect() as db:db.execute("UPDATE revisions SET status='failed' WHERE task_id=?",(id,))
        finally:
            with self.lock:
                self.active = None
                self.signals.pop(id, None)
        return True

    def request_visual_review(self,id):
        from backend.visual_review import fingerprint,CAPTURE_VERSION
        from backend.revisions import published
        parent=self.store.task(id)
        if parent['status'] in ('running','queued'):
            raise ValueError('Aguarde a criação do artefato terminar')
        with self.store.connect() as db:
            artifact=db.execute('SELECT task_id FROM artifacts WHERE task_id=?',(id,)).fetchone()
        if not artifact:raise ValueError('Não há artefato para visualizar')
        path=published(self.store,id)
        digest=fingerprint(path)
        review_id=self.store.create('Revisão visual do artefato '+id,parent['project_id'],'auto','visual-review:v'+str(CAPTURE_VERSION)+':'+id+':'+digest,
                                    'visual_review',{'parent_id':id,'artifact_digest':digest,'capture_version':CAPTURE_VERSION,'artifact_slug':path.name})
        with self.store.connect() as db:
            db.execute('INSERT OR IGNORE INTO visual_reviews(task_id,parent_id,time) VALUES(?,?,?)',(review_id,id,now()))
            state=self.store.task(review_id)['status']
            revision_state='ready' if state=='completed' else 'review_failed' if state in ('failed','blocked','cancelled','interrupted') else 'reviewing'
            db.execute("UPDATE revisions SET after_review_id=?,status=CASE WHEN status IN ('accepted','restored') THEN status ELSE ? END WHERE task_id=?",(review_id,revision_state,id))
            self.store.event(db,id,'visual_review_requested',{'review_task_id':review_id,'artifact_digest':digest})
        return review_id

    def run_visual_review(self,task,emit,cancel):
        from backend.visual_review import capture,review_prompt,fingerprint
        from backend.artifacts import workspace
        spec=json.loads(task['spec']);parent=self.store.task(spec['parent_id']);path=workspace(spec.get('artifact_slug',parent['id']))
        if fingerprint(path)!=spec['artifact_digest']:
            raise ValueError('O artefato mudou antes da revisão. Solicite uma captura da versão atual.')
        emit('visual_capture_started',{'parent_id':parent['id']})
        report,images=capture(path.name,task['id'],cancel)
        if fingerprint(path)!=spec['artifact_digest']:
            raise ValueError('O artefato mudou durante a captura; revisão não enviada ao agente.')
        with self.store.connect() as db:
            db.execute('UPDATE visual_reviews SET capture=? WHERE task_id=?',(json.dumps(report,ensure_ascii=False),task['id']))
            self.store.event(db,task['id'],'visual_capture_completed',{'images':len(images),'page_errors':len(report.get('page_errors',[]))})
        if cancel.is_set():return {'status':'cancelled','result':'','usage':{},'error':'Revisão cancelada antes da chamada visual'}
        prompt_parent=parent
        comparison=''
        if parent['workflow']=='improve':
            improvement=json.loads(parent['spec'])
            prompt_parent=dict(parent)
            prompt_parent['objective']=self.store.task(improvement['parent_id'])['objective']
            with self.store.connect() as db:
                before=db.execute('SELECT capture FROM visual_reviews WHERE task_id=?',(improvement['review_id'],)).fetchone()
            before_images=json.loads(before[0]).get('images',[]) if before else []
            wanted={name for proposal in improvement['proposals'] for name in ('desktop.png','interaction.png','mobile.png') if name in proposal.get('capture','')}
            if not wanted:
                wanted={'mobile.png'} if any(word in improvement['feedback'].casefold() for word in ('mobile','celular','touch')) else {'interaction.png'}
            references=[i for i in before_images if i['name'] in wanted] or before_images[:1]
            if references:
                from backend.visual_review import EVIDENCE
                import hashlib
                after_count=len(images);mapping=[]
                for before_image in references:
                    before_path=EVIDENCE/improvement['review_id']/before_image['name']
                    if before_path.is_symlink() or not before_path.is_file() or hashlib.sha256(before_path.read_bytes()).hexdigest()!=before_image['sha256']:
                        raise ValueError('Imagem anterior alterada; comparação não realizada')
                    images.append(str(before_path));mapping.append({'name':before_image['name'],'image_index':len(images)})
                report['comparison']={'before_review_id':improvement['review_id'],'before_images':mapping,'after_image_count':after_count,'criteria':improvement['proposals'],'feedback':improvement['feedback']}
                comparison='\nCOMPARAÇÃO OBRIGATÓRIA: As primeiras '+str(after_count)+' imagens são DEPOIS, na ordem do relatório. As imagens seguintes são ANTES: '+json.dumps(mapping)+'. Para cada critério selecionado classifique atendido, parcial, não atendido ou não verificável, citando diferenças realmente visíveis. Não atribua melhorias a partir de código ou de uma promessa. Critérios e feedback: '+json.dumps({'proposals':improvement['proposals'],'feedback':improvement['feedback']},ensure_ascii=False)
                with self.store.connect() as db:db.execute('UPDATE visual_reviews SET capture=? WHERE task_id=?',(json.dumps(report,ensure_ascii=False),task['id']))
        active_adapter = self.adapters.get(task.get('provider'), self.adapter)
        if hasattr(active_adapter, 'execute_visual'):
            result = active_adapter.execute_visual(review_prompt(prompt_parent,report)+comparison,str(path),emit,cancel,images)
        else:
            result = active_adapter.execute(review_prompt(prompt_parent,report)+comparison,str(path),emit,cancel)
        if result['status'] != 'completed' and not cancel.is_set():
            err_msg = result.get('error') or ''
            is_quota = result['status'] == 'rate_limited' or any(k in err_msg.lower() for k in ('usage limit', 'rate limit', 'quota'))
            if is_quota or result['status'] == 'failed':
                failover = Decision.decide_failover(task, task.get('provider', 'codex'), err_msg, self.providers())
                if failover:
                    alt_provider = failover['selected_provider']
                    emit('provider_failover', {
                        'from_provider': task.get('provider', 'codex'),
                        'to_provider': alt_provider,
                        'reason': failover['reason'],
                        'confidence': failover['confidence']
                    })
                    with self.store.connect() as db:
                        db.execute('UPDATE tasks SET provider=?, routing=? WHERE id=?',
                                   (alt_provider, json.dumps(failover, ensure_ascii=False), task['id']))
                        self.store.event(db, task['id'], 'provider_failover', failover)
                    task['provider'] = alt_provider
                    alt_adapter = self.adapters.get(alt_provider, self.adapter)
                    if hasattr(alt_adapter, 'execute_visual'):
                        result = alt_adapter.execute_visual(review_prompt(prompt_parent,report)+comparison,str(path),emit,cancel,images)
                    else:
                        result = alt_adapter.execute(review_prompt(prompt_parent,report)+comparison,str(path),emit,cancel)
        if fingerprint(path)!=spec['artifact_digest']:
            result['status']='needs_review';result['error']='O artefato mudou após a captura; relatório refere-se às imagens anteriores.'
        with self.store.connect() as db:
            db.execute('UPDATE visual_reviews SET report=? WHERE task_id=?',(result['result'],task['id']))
            db.execute("UPDATE revisions SET status=? WHERE after_review_id=? AND status NOT IN ('accepted','restored')",('ready' if result['status']=='completed' and not report.get('page_errors') and not report.get('failed_requests') else 'review_failed',task['id']))
            self.store.event(db,parent['id'],'visual_review_finished',{'review_task_id':task['id'],'status':result['status']})
        return result

    def request_improvements(self,parent_id,review_id,ids,feedback=''):
        from backend.revisions import published,suggestions
        from backend.visual_review import fingerprint
        if not isinstance(ids,list) or not all(isinstance(i,str) for i in ids) or not isinstance(feedback,str) or len(feedback)>4000:
            raise ValueError('Seleção de melhorias inválida')
        with self.lock:
            parent=self.store.task(parent_id)
            if parent['status'] in ('running','queued'):raise ValueError('Aguarde a tarefa ativa')
            with self.store.connect() as db:review=db.execute('SELECT * FROM visual_reviews WHERE task_id=? AND parent_id=?',(review_id,parent_id)).fetchone()
            if not review or self.store.task(review_id)['status']!='completed':raise ValueError('Revisão visual concluída não encontrada')
            available={p['id']:p for p in suggestions(review['report'])}
            if set(ids)-set(available):raise ValueError('Proposta não pertence a esta revisão')
            if not ids and not feedback.strip():raise ValueError('Selecione uma proposta ou descreva o ajuste')
            path=published(self.store,parent_id);digest=fingerprint(path)
            if json.loads(self.store.task(review_id)['spec'])['artifact_digest']!=digest:
                raise ValueError('A revisão é de outra versão. Analise a versão atual antes de aplicar melhorias.')
            proposals=[available[i] for i in sorted(set(ids))]
            spec={'parent_id':parent_id,'review_id':review_id,'base_path':str(path),'base_hash':digest,'proposals':proposals,'feedback':feedback.strip()}
            import hashlib
            key='improve:'+parent_id+':'+hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()
            id=self.store.create('Melhorar artefato '+parent_id,parent['project_id'],'auto',key,'improve',spec)
            with self.store.connect() as db:
                db.execute('INSERT OR IGNORE INTO revisions(task_id,parent_id,source_review_id,base_path,base_hash,status,created_at) VALUES(?,?,?,?,?,?,?)',(id,parent_id,review_id,str(path),digest,'queued',now()))
                self.store.event(db,parent_id,'improvements_requested',{'revision_task_id':id,'proposals':[p['id'] for p in proposals]})
            return id

    def run_improvements(self,task,emit,cancel):
        from backend.revisions import safe_path,clone,changed,improvement_prompt
        from backend.visual_review import fingerprint,EVIDENCE
        from backend.artifacts import inventory,validate
        spec=json.loads(task['spec']);base=safe_path(spec['base_path'])
        if fingerprint(base)!=spec['base_hash']:raise ValueError('A versão base mudou; nenhuma alteração foi aplicada')
        candidate=clone(base,task['id'])
        with self.store.connect() as db:
            done=db.execute("SELECT output FROM task_steps WHERE task_id=? AND stage='improve_implement'",(task['id'],)).fetchone()
            review=db.execute('SELECT capture FROM visual_reviews WHERE task_id=?',(spec['review_id'],)).fetchone()
        images=[]
        for item in json.loads(review[0]).get('images',[]):
            path=EVIDENCE/spec['review_id']/item['name']
            if item['name'] not in ('desktop.png','interaction.png','mobile.png') or path.is_symlink() or not path.is_file():raise ValueError('Evidência anterior inválida')
            import hashlib
            if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Evidência anterior alterada')
            images.append(str(path))
        usage={};summary=done[0] if done else ''
        if not done:
            emit('revision_snapshot_created',{'base_path':str(base),'candidate_path':str(candidate)})
            with self.store.connect() as db:db.execute("UPDATE revisions SET status='editing' WHERE task_id=?",(task['id'],))
            active_adapter = self.adapters.get(task.get('provider'), self.adapter)
            if hasattr(active_adapter, 'execute_improvements'):
                result = active_adapter.execute_improvements(improvement_prompt(spec),str(candidate),emit,cancel,images)
            else:
                from backend.agent_engine import run_universal_agent
                result = run_universal_agent(active_adapter, improvement_prompt(spec), str(candidate), emit, cancel, timeout=1200)
            if result['status'] != 'completed' and not cancel.is_set():
                err_msg = result.get('error') or ''
                is_quota = result['status'] == 'rate_limited' or any(k in err_msg.lower() for k in ('usage limit', 'rate limit', 'quota'))
                if is_quota or result['status'] == 'failed':
                    failover = Decision.decide_failover(task, task.get('provider', 'codex'), err_msg, self.providers())
                    if failover:
                        alt_provider = failover['selected_provider']
                        emit('provider_failover', {
                            'from_provider': task.get('provider', 'codex'),
                            'to_provider': alt_provider,
                            'reason': failover['reason'],
                            'confidence': failover['confidence']
                        })
                        with self.store.connect() as db:
                            db.execute('UPDATE tasks SET provider=?, routing=? WHERE id=?',
                                       (alt_provider, json.dumps(failover, ensure_ascii=False), task['id']))
                            self.store.event(db, task['id'], 'provider_failover', failover)
                        task['provider'] = alt_provider
                        alt_adapter = self.adapters.get(alt_provider, self.adapter)
                        if hasattr(alt_adapter, 'execute_improvements'):
                            result = alt_adapter.execute_improvements(improvement_prompt(spec),str(candidate),emit,cancel,images)
                        else:
                            from backend.agent_engine import run_universal_agent
                            result = run_universal_agent(alt_adapter, improvement_prompt(spec), str(candidate), emit, cancel, timeout=1200)
            if result['status'] != 'completed': return result
            summary=result['result'];usage=result['usage']
            if cancel.is_set():return {'status':'cancelled','result':summary,'usage':usage,'error':'Melhoria cancelada; candidata não publicada'}
            with self.store.connect() as db:
                db.execute('INSERT INTO task_steps VALUES(?,?,?,?)',(task['id'],'improve_implement',summary,now()))
                self.store.checkpoint(db,self.store.task(task['id']))
        if fingerprint(base)!=spec['base_hash']:raise ValueError('Integridade da versão base falhou; candidata não publicada')
        report=validate(candidate);diff=changed(inventory(base),report['files']);diff['after_hash']=fingerprint(candidate)
        protected=[p for p in diff['added']+diff['modified']+diff['removed'] if p.startswith(('vendor/','planning/'))]
        if protected:
            report['passed']=False;report['checks'].append({'check':'protected_files_preserved','passed':False,'files':protected})
        with self.store.connect() as db:
            db.execute('INSERT OR REPLACE INTO artifacts VALUES(?,?,?,?)',(task['id'],str(candidate),json.dumps(report,ensure_ascii=False),now()))
            db.execute('UPDATE revisions SET status=?,changes=?,validation=? WHERE task_id=?',('validated' if report['passed'] else 'validation_failed',json.dumps(diff),json.dumps(report),task['id']))
            self.store.event(db,task['id'],'revision_validated',{'passed':report['passed'],'changes':diff})
        return {'status':'completed' if report['passed'] else 'needs_review','result':summary+'\n\nVersão candidata: '+report['preview_url']+'\nA versão publicada permanece intacta; aguarde a revisão visual e aceite para substituir.','usage':usage,'error':None if report['passed'] else 'Validação da candidata falhou; original preservado'}

    def publish_revision(self,id,restore=False):
        from backend.revisions import safe_path,published
        from backend.visual_review import fingerprint
        from backend.artifacts import validate
        with self.lock:
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                row=db.execute('SELECT * FROM revisions WHERE task_id=?',(id,)).fetchone()
                if not row:raise ValueError('Versão não encontrada')
                if self.active:raise ValueError('Aguarde a execução ativa antes de trocar a versão')
                current=published(self.store,row['parent_id']);base=safe_path(row['base_path'])
                if restore:
                    if row['status']!='accepted' or current.name!=id:raise ValueError('Somente a versão ativa pode ser restaurada')
                    target=base;status='restored'
                else:
                    if row['status'] not in ('ready','restored'):raise ValueError('Aguarde validação e revisão visual concluídas')
                    if fingerprint(current)!=row['base_hash']:raise ValueError('A versão publicada mudou; não substituir automaticamente')
                    target=safe_path(__import__('backend.artifacts',fromlist=['OUTPUT']).OUTPUT/id)
                    if fingerprint(target)!=json.loads(row['changes'])['after_hash']:raise ValueError('A candidata mudou após a validação')
                    status='accepted'
                if fingerprint(base)!=row['base_hash']:raise ValueError('Snapshot anterior mudou')
                report=validate(target)
                if not report['passed']:raise ValueError('A versão escolhida não passou na validação estrutural')
                db.execute('UPDATE artifacts SET path=?,manifest=?,time=? WHERE task_id=?',(str(target),json.dumps(report,ensure_ascii=False),now(),row['parent_id']))
                db.execute('UPDATE revisions SET status=? WHERE task_id=?',(status,id))
                db.execute("UPDATE tasks SET quality='unreviewed' WHERE id=?",(row['parent_id'],))
                self.store.event(db,row['parent_id'],'revision_'+status,{'revision_task_id':id,'active_path':str(target)})
                self.store.checkpoint(db,self.store.task(row['parent_id']))
            return {'ok':True,'preview_url':report['preview_url']}

    def implement(self,id):
        with self.lock:
            task=self.store.task(id)
            if task['workflow']!='rea':raise ValueError('Use o ciclo de melhorias para um artefato já implementado')
            if task['status'] not in ('completed','needs_review','failed','interrupted'):
                raise ValueError('Aguarde a tarefa terminar antes de implementar')
            with self.store.connect() as db:
                stages={r[0] for r in db.execute('SELECT stage FROM task_steps WHERE task_id=?',(id,))}
                if not {'research','evaluate','architect'}.issubset(stages):
                    raise ValueError('Conclua as três etapas REA antes da implementação')
                db.execute("UPDATE tasks SET workflow='deliver',provider='auto',requested_provider='auto' WHERE id=?",(id,))
                self.store.event(db,id,'implementation_requested',{'scope':'workspace isolado','reuse_research':True})
            self.store.update(id,'queued',error=None)

    def run_delivery(self,task,emit,cancel):
        from backend.artifacts import prepare,validate
        with self.store.connect() as db:
            steps=[dict(r) for r in db.execute('SELECT * FROM task_steps WHERE task_id=? ORDER BY time',(task['id'],))]
        path=prepare(task,steps)
        done={s['stage'] for s in steps}
        usage={}
        summary='Implementação confirmada em execução anterior.'
        if 'implement' not in done:
            emit('implementation_started',{'workspace':str(path)})
            prompt=('Implemente de verdade o produto descrito em planning/objective.md, aproveitando planning/architect.md e planning/evaluate.md. A pesquisa já foi feita: não refaça pesquisa nem navegação. '
                    'Seu único diretório gravável de produto é este workspace isolado. Crie arquivos reais, não apenas código na resposta. '
                    'Entregue um primeiro MVP funcional de navegador em index.html, style.css e main.js (pode modularizar). Sem npm install ou serviços externos: Three.js já está em vendor/three.module.js e vendor/three.core.js; importe por caminho relativo. '
                    'Não modifique planning/ nem vendor/, não toque em outros projetos, credenciais ou configuração. Não publique nem execute operações destrutivas. '
                    'Crie experiência visual cuidada com gameplay 3D verdadeiro, materiais/iluminação, cenário legível, controle WASD e mouse, tiro, zumbis, colisões, vida, derrota/reinício, progressão e chefe se couber. '
                    'Use geometria procedural própria e áudio sintetizado, sem assets remotos. Priorize núcleo realmente jogável e indique claramente requisitos ainda pendentes. '
                    'Menus com botão Jogar e instruções em português; o jogo deve funcionar por servidor estático com caminhos relativos. '
                    'Expose window.__gameTest com getState() para inspeção de estado de jogo (tempo, inimigos, vida, pontuação) sem atalhos de vitória. '
                    'Registre controles, estado implementado, limitações e validações reais em README.md, PROJECT_STATE.md e QA_REPORT.md. Rode node --check nos seus JS. '
                    'Esta etapa autoriza escrever código dentro deste workspace: não se limite a planejar. Produza o MVP agora.')
            active_adapter = self.adapters.get(task.get('provider'), self.adapter)
            if hasattr(active_adapter, 'execute_build'):
                result = active_adapter.execute_build(prompt, str(path), emit, cancel)
            else:
                from backend.agent_engine import run_universal_agent
                result = run_universal_agent(active_adapter, prompt, str(path), emit, cancel, timeout=1200)
            if result['status'] != 'completed' and not cancel.is_set():
                err_msg = result.get('error') or ''
                is_quota = result['status'] == 'rate_limited' or any(k in err_msg.lower() for k in ('usage limit', 'rate limit', 'quota'))
                if is_quota or result['status'] == 'failed':
                    failover = Decision.decide_failover(task, task.get('provider', 'codex'), err_msg, self.providers())
                    if failover:
                        alt_provider = failover['selected_provider']
                        emit('provider_failover', {
                            'from_provider': task.get('provider', 'codex'),
                            'to_provider': alt_provider,
                            'reason': failover['reason'],
                            'confidence': failover['confidence']
                        })
                        with self.store.connect() as db:
                            db.execute('UPDATE tasks SET provider=?, routing=? WHERE id=?',
                                       (alt_provider, json.dumps(failover, ensure_ascii=False), task['id']))
                            self.store.event(db, task['id'], 'provider_failover', failover)
                        task['provider'] = alt_provider
                        alt_adapter = self.adapters.get(alt_provider, self.adapter)
                        if hasattr(alt_adapter, 'execute_build'):
                            result = alt_adapter.execute_build(prompt, str(path), emit, cancel)
                        else:
                            from backend.agent_engine import run_universal_agent
                            result = run_universal_agent(alt_adapter, prompt, str(path), emit, cancel, timeout=1200)
            usage = result['usage']; summary = result['result']
            if result['status'] != 'completed': return result
            # Require generated executable files before recording implementation success.
            if not (path/'index.html').is_file():
                return {'status':'failed','result':summary,'usage':usage,'error':'Agente não criou index.html. Relatório textual não é implementação.'}
            with self.store.connect() as db:
                db.execute('INSERT INTO task_steps VALUES(?,?,?,?)',(task['id'],'implement',summary,now()))
                self.store.checkpoint(db,self.store.task(task['id']))
                self.store.event(db,task['id'],'implementation_completed',{'workspace':str(path)})
        report=validate(path)
        with self.store.connect() as db:
            db.execute('INSERT OR REPLACE INTO artifacts VALUES(?,?,?,?)',(task['id'],str(path),json.dumps(report,ensure_ascii=False),now()))
            if report['passed']:
                db.execute('INSERT OR REPLACE INTO task_steps VALUES(?,?,?,?)',(task['id'],'validate',json.dumps(report,ensure_ascii=False),now()))
            db.execute('UPDATE tasks SET validation=? WHERE id=?',(json.dumps({'status':'passed' if report['passed'] else 'failed','check':'artifact_structure_and_javascript_syntax','semantic_quality':'requires_browser_review'}),task['id']))
            self.store.event(db,task['id'],'artifact_validated',{'passed':report['passed'],'preview_url':report['preview_url']})
        return {'status':'completed' if report['passed'] else 'needs_review','result':summary+'\n\nArtefato: '+report['preview_url']+'\n'+report['scope'],'usage':usage,'error':None if report['passed'] else 'Artefatos criados, mas validação estrutural falhou.'}

    def run_rea(self, task, prompt, cwd, adapter, emit, cancel):
        with self.store.connect() as db:
            done = {r['stage']: r['output'] for r in db.execute('SELECT * FROM task_steps WHERE task_id=?', (task['id'],))}
        usage = {}
        for stage, instruction in REA_STAGES:
            if stage in done:
                continue
            if cancel.is_set():
                return {'status': 'cancelled', 'result': json.dumps(done, ensure_ascii=False), 'usage': usage, 'error': 'Cancelado entre etapas REA'}
            emit('rea_stage_started', {'stage': stage})
            context = json.dumps(done, ensure_ascii=False)
            if len(context) > 120000:
                raise ValueError('Contexto REA excede orçamento; etapas confirmadas preservadas, sem truncamento.')
            execute_stage = getattr(adapter, 'execute_report', adapter.execute)
            stage_prompt = 'ETAPA REA ATUAL: '+stage.upper()+'. Entregue uma resposta textual pública nesta chamada. O objetivo abaixo é referência para esta etapa; não execute sua implementação integral, não solicite interação nem crie artefatos.\n'+prompt+'\n'+instruction+'\nEtapas confirmadas: '+context+'\nResponda agora com o relatório textual da etapa '+stage+'.'
            if hasattr(adapter, 'chat_turn'):
                from backend.agent_engine import run_universal_agent
                result = run_universal_agent(adapter, stage_prompt, cwd, emit, cancel, read_only=True)
                result.pop('files_mutated', None)
            else:
                result = execute_stage(stage_prompt, cwd, emit, cancel)
            if (not cancel.is_set() and task['provider']=='antigravity' and result['status']=='failed'
                    and (result.get('error') or '').startswith('Antigravity encerrou com SUCCESS, mas sem resposta pública')
                    and self.adapter.probe().get('state')=='available'):
                # A bounded read-only stage fallback, never a rate-limit/auth bypass.
                failed_usage=result['usage']
                decision={'selected':'codex','reason':'Gemini encerrou a etapa sem resposta pública; continuar a mesma etapa REA somente leitura com Codex, preservando etapas confirmadas.'}
                with self.store.connect() as db:
                    db.execute('UPDATE tasks SET provider=?,routing=? WHERE id=?',('codex',json.dumps(decision,ensure_ascii=False),task['id']))
                    self.store.event(db,task['id'],'rea_stage_provider_changed',{'stage':stage,**decision})
                task['provider']='codex'
                adapter=self.adapter
                result=adapter.execute(stage_prompt,cwd,emit,cancel)
                result['usage']={k:failed_usage.get(k,0)+result['usage'].get(k,0) for k in set(failed_usage)|set(result['usage'])}

            for k, v in result['usage'].items():
                if isinstance(v, (int, float)):
                    usage[k] = usage.get(k, 0)+v
            if result['status'] != 'completed':
                result['usage'] = usage
                return result
            with self.store.connect() as db:
                db.execute('INSERT INTO task_steps VALUES(?,?,?,?)', (task['id'], stage, result['result'], now()))
                self.store.checkpoint(db, self.store.task(task['id']))
                self.store.event(db, task['id'], 'rea_stage_completed', {'stage': stage})
            done[stage] = result['result']
        return {'status': 'completed', 'result': '\n\n'.join(k.upper()+'\n'+v for k, v in done.items()), 'usage': usage, 'error': None}

    def loop(self):
        while True:
            try:
                self.run_once()
            except Exception:
                # Keep the worker alive even when routing or persistence fails before task execution.
                logging.exception('Supervisor iteration failed; pending work remains persisted')
                time.sleep(2)
            time.sleep(.3)
