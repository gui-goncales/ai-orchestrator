import argparse
import json
import mimetypes
import os
import signal
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from backend.core import Store, Supervisor, now, handoff

ROOT = Path(__file__).resolve().parent.parent


def serve(port=8787, data=None, adapter=None):
    store = Store(data or ROOT/'data'/'orchestrator.sqlite3', ROOT)
    supervisor = Supervisor(store, adapter)
    # Refuse a second backend for the same DB (POSIX local target).
    import fcntl
    lease = open(store.path+'.lock', 'w')
    try:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('Outro backend já utiliza este banco.')
    store.recover()
    origin = 'http://127.0.0.1:'+str(port)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def headers_ok(self):
            return self.headers.get('Host') == '127.0.0.1:'+str(port) and self.headers.get('Origin', origin) == origin

        def send(self, value, status=200):
            raw = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if not self.headers_ok():
                return self.send({'error': 'Origem não autorizada'}, 403)
            path = urlparse(self.path).path
            if path == '/api/browser-bridge/next':
                from backend.browser_bridge import bridge
                return self.send({'job': bridge.next_job()})
            if path == '/api/health':
                return self.send({'app':'ai-orchestrator','status':'online','pid':os.getpid(),'time':now()})
            if path == '/api/state':
                return self.send({**store.snapshot(), 'providers': supervisor.providers(), 'server_time': now()})
            if path.startswith('/api/reviews/') and '/evidence/' in path:
                from backend.visual_review import EVIDENCE
                parts=path.split('/')
                if len(parts)!=6 or parts[5] not in ('desktop.png','interaction.png','mobile.png'):
                    return self.send({'error':'Evidência inválida'},404)
                id=parts[3]
                with store.connect() as db:
                    review=db.execute('SELECT capture FROM visual_reviews WHERE task_id=?',(id,)).fetchone()
                if not review or parts[5] not in [i['name'] for i in json.loads(review[0]).get('images',[])]:
                    return self.send({'error':'Captura não registrada'},404)
                image=EVIDENCE/id/parts[5]
                if image.is_symlink() or not image.is_file():return self.send({'error':'Captura ausente'},404)
                raw=image.read_bytes();self.send_response(200)
                self.send_header('Content-Type','image/png');self.send_header('Content-Length',str(len(raw)))
                self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
                self.end_headers();self.wfile.write(raw);return
            if path.startswith('/api/artifacts/') and path.endswith('/download'):
                import io,zipfile
                from backend.artifacts import inventory,workspace
                id=path.split('/')[3]
                with store.connect() as db:
                    artifact=db.execute('SELECT task_id FROM artifacts WHERE task_id=?',(id,)).fetchone()
                if not artifact:return self.send({'error':'Artefato não encontrado'},404)
                from backend.revisions import published
                folder=published(store,id);buffer=io.BytesIO()
                with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
                    for item in inventory(folder):archive.write(folder/item['path'],item['path'])
                raw=buffer.getvalue();self.send_response(200)
                self.send_header('Content-Type','application/zip')
                self.send_header('Content-Disposition','attachment; filename="artifact-'+id+'.zip"')
                self.send_header('Content-Length',str(len(raw)))
                self.send_header('Cache-Control','no-store')
                self.end_headers();self.wfile.write(raw);return
            if path == '/api/events':
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                try:
                    while True:
                        with store.connect() as db:
                            revision = db.execute('SELECT COALESCE(MAX(id),0) FROM events').fetchone()[0]
                        self.wfile.write(('data: '+json.dumps({'revision': revision})+'\n\n').encode())
                        self.wfile.flush()
                        time.sleep(2)
                except (BrokenPipeError, ConnectionResetError):
                    return
            if path.startswith('/api/'):
                return self.send({'error': 'Não encontrado'}, 404)
            base = ROOT/'frontend'/'dist'
            target = (base/path.lstrip('/')).resolve()
            if not target.is_relative_to(base.resolve()):
                return self.send({'error': 'Caminho inválido'}, 403)
            if not target.is_file():
                if path != '/':
                    return self.send({'error': 'Arquivo não encontrado'}, 404)
                target = base/'index.html'
            if not target.is_file():
                return self.send({'error': 'Execute npm --prefix frontend run build'}, 503)
            raw = target.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', mimetypes.guess_type(str(target))[0] or 'application/octet-stream')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            if not self.headers_ok() or self.headers.get('Content-Type') != 'application/json':
                return self.send({'error': 'Origem ou tipo inválido'}, 403)
            try:
                size = int(self.headers.get('Content-Length', 0))
                if size <= 0 or size > 64000:
                    raise ValueError('Corpo inválido')
                body = json.loads(self.rfile.read(size))
                path = urlparse(self.path).path
                if path.startswith('/api/browser-bridge/') and path.endswith('/result'):
                    from backend.browser_bridge import bridge
                    job_id = path.split('/')[3]
                    return self.send({'ok': bridge.complete(job_id, body)})
                if path == '/api/providers':
                    return self.send(supervisor.save_provider(body), 201)
                if path.startswith('/api/providers/'):
                    _, _, _, provider_id, action = path.split('/')
                    return self.send(supervisor.provider_action(provider_id, action))
                if path == '/api/tasks':
                    if body.get('provider') == 'rea':
                        from backend.integrations import ReaAdapter
                        with store.connect() as db:
                            project = db.execute('SELECT path FROM projects WHERE id=?', (body.get('project_id', 'local'),)).fetchone()
                        if not project:
                            raise ValueError('Projeto não encontrado')
                        ReaAdapter.target(body.get('spec') or {}, project[0])
                    id = store.create(body.get('objective', ''), body.get('project_id', 'local'), body.get('provider', 'auto'), self.headers.get('Idempotency-Key'), body.get('workflow', 'direct'), body.get('spec'))
                    return self.send({'id': id}, 201)
                if path.startswith('/api/tasks/'):
                    _, _, _, id, action = path.split('/')
                    if action == 'delete':
                        return self.send(store.delete_conversation(id))
                    if action == 'cancel':
                        supervisor.cancel(id)
                    elif action == 'resume':
                        supervisor.resume(id)
                    elif action == 'improve':
                        return self.send({'id':supervisor.request_improvements(id,body.get('review_id'),body.get('proposal_ids',[]),body.get('feedback',''))},201)
                    elif action == 'accept-version':
                        return self.send(supervisor.publish_revision(id))
                    elif action == 'restore-version':
                        return self.send(supervisor.publish_revision(id,restore=True))
                    elif action == 'visual-review':
                        return self.send({'id':supervisor.request_visual_review(id)},201)
                    elif action == 'implement':
                        supervisor.implement(id)
                    elif action == 'accept':
                        if store.task(id)['status'] not in ('completed','needs_review'):
                            raise ValueError('Sem resultado para validar')
                        with store.connect() as db:
                            db.execute("UPDATE tasks SET quality='accepted' WHERE id=?",(id,))
                            store.event(db,id,'quality_accepted',{'origin':'user'})
                    elif action == 'handoff':
                        return self.send(handoff(store.task(id)))
                    else:
                        raise ValueError('Ação desconhecida')
                    return self.send({'ok': True})
                if path == '/api/memory':
                    content = body.get('content', '').strip()
                    if not content or len(content) > 20000:
                        raise ValueError('Memória inválida')
                    with store.connect() as db:
                        id = body.get('id') or uuid.uuid4().hex[:12]
                        project = body.get('project_id', 'local')
                        if not db.execute('SELECT id FROM projects WHERE id=?', (project,)).fetchone():
                            raise ValueError('Projeto inválido')
                        kind=body.get('kind','constraint')
                        if kind not in ('constraint','reference'):
                            raise ValueError('Tipo de memória inválido')
                        db.execute('INSERT INTO memory(id,project_id,content,time,kind) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET content=excluded.content,time=excluded.time,kind=excluded.kind', (id, project, content, now(),kind))
                        store.event(db, None, 'memory_saved', {'id': id})
                    return self.send({'id': id})
                if path == '/api/memory/delete':
                    with store.connect() as db:
                        db.execute('DELETE FROM memory WHERE id=?', (body.get('id'),))
                        store.event(db, None, 'memory_deleted', {'id': body.get('id')})
                    return self.send({'ok': True})
                if path == '/api/projects/context':
                    from backend.agent_engine import WorkspaceTools
                    with store.connect() as db:
                        project = db.execute('SELECT * FROM projects WHERE id=?', (body.get('project_id'),)).fetchone()
                    if not project or not Path(project['path']).is_dir():
                        raise ValueError('Pasta do projeto indisponível')
                    tools = WorkspaceTools(project['path'], read_only=True)
                    operation = 'read_file' if body.get('file') else 'list_dir'
                    return self.send(tools.dispatch(operation, {'path': body.get('file') or body.get('path', '.')}))
                if path == '/api/projects':
                    name = body.get('name', '').strip()
                    # Explicit local directory registration, no arbitrary shell commands.
                    folder = Path(body.get('path', '')).expanduser().resolve()
                    if not name or len(name) > 100 or not folder.is_dir():
                        raise ValueError('Nome ou diretório inválido')
                    with store.connect() as db:
                        id = body.get('id') or uuid.uuid4().hex[:12]
                        if body.get('id') and not db.execute('SELECT id FROM projects WHERE id=?', (id,)).fetchone():
                            raise ValueError('Projeto não encontrado')
                        if db.execute("SELECT 1 FROM tasks WHERE project_id=? AND status IN ('running','queued')", (id,)).fetchone():
                            raise ValueError('Aguarde as tarefas antes de trocar a pasta')
                        db.execute('INSERT INTO projects VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,path=excluded.path', (id, name, str(folder)))
                        store.event(db, None, 'project_created', {'id': id})
                    return self.send({'id': id})
                return self.send({'error': 'Não encontrado'}, 404)
            except (ValueError, TypeError, AttributeError, KeyError) as e:
                return self.send({'error': str(e)}, 400)

    from backend.artifacts import start_preview
    preview=start_preview() if port==8787 else None
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    threading.Thread(target=supervisor.loop, daemon=True).start()
    connection_stop = threading.Event()
    if adapter is None:
        threading.Thread(target=supervisor.connection_loop, args=(connection_stop,), daemon=True).start()
    def interrupt(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupt)
    print('AI Orchestrator: '+origin, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        connection_stop.set()
        with supervisor.lock:
            for event in supervisor.signals.values():
                event.set()
        deadline = time.monotonic()+5
        while supervisor.active and time.monotonic() < deadline:
            time.sleep(.1)
        server.server_close()
        if preview:preview.shutdown();preview.server_close()
        lease.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8787)
    parser.add_argument('--data')
    args = parser.parse_args()
    serve(args.port, args.data)
