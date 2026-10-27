"""Isolated artifact workspaces, deterministic validation, separate preview origin."""
import hashlib
import json
import mimetypes
import re
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote,urlparse

ROOT=Path(__file__).resolve().parent.parent
OUTPUT=ROOT/'artifacts'


def workspace(task_id):
    if not re.fullmatch(r'[a-f0-9]{12}',task_id):raise ValueError('ID de artefato inválido')
    path=OUTPUT/task_id
    path.mkdir(parents=True,exist_ok=True)
    if path.is_symlink() or not path.resolve().is_relative_to(OUTPUT.resolve()):raise ValueError('Workspace inválido')
    return path


def inventory(path):
    files=[]
    for p in sorted(path.rglob('*')):
        if p.is_symlink():raise ValueError('Symlinks não são permitidos nos artefatos')
        if not p.is_file() or any(part in ('.git','node_modules','.codex') for part in p.relative_to(path).parts):continue
        if p.stat().st_size>20*1024*1024:raise ValueError('Arquivo excede o limite de 20 MiB')
        files.append({'path':p.relative_to(path).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    return files


def prepare(task,steps):
    path=workspace(task['id'])
    docs=path/'planning';docs.mkdir(exist_ok=True)
    for step in steps:
        if step['stage'] in ('research','evaluate','architect'):
            (docs/(step['stage']+'.md')).write_text(step['output'])
    (docs/'objective.md').write_text(task['objective'])
    vendor=path/'vendor';vendor.mkdir(exist_ok=True)
    source=ROOT/'node_modules'/'three'/'build'
    for name in ('three.module.js','three.core.js'):
        if (source/name).exists() and not (vendor/name).exists():shutil.copy2(source/name,vendor/name)
    license=ROOT/'node_modules'/'three'/'LICENSE'
    if license.exists():shutil.copy2(license,vendor/'THREE-LICENSE.txt')
    if not (path/'package.json').exists():
        (path/'package.json').write_text(json.dumps({'name':'artifact-'+task['id'],'version':'0.1.0','private':True,'type':'module'}))
    return path


def validate(path):
    files=inventory(path)
    checks=[]
    checks.append({'check':'html_entry','passed':(path/'index.html').is_file() and (path/'index.html').stat().st_size>0})
    app_js=[f for f in files if f['path'].endswith(('.js','.mjs')) and not f['path'].startswith('vendor/')]
    checks.append({'check':'application_javascript','passed':bool(app_js)})
    node=shutil.which('node')
    if not node:raise ValueError('Node necessário para validar sintaxe')
    for item in app_js:
        # Parsing only. Never execute model-generated npm/package scripts in the backend.
        r=subprocess.run([node,'--check',str(path/item['path'])],capture_output=True,text=True,timeout=20)
        checks.append({'check':'javascript_syntax','file':item['path'],'passed':r.returncode==0,'error':r.stderr[-2000:] if r.returncode else None})
    return {'passed':all(c['passed'] for c in checks),'checks':checks,'files':files,
            'scope':'Validação estrutural e sintática. Jogabilidade, desempenho e qualidade visual exigem testes de navegador e revisão.',
            'preview_url':'http://127.0.0.1:8789/'+path.name+'/'}


def start_preview(port=8789):
    class Preview(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.headers.get('Host')!='127.0.0.1:'+str(port):self.send_error(403);return
            parts=unquote(urlparse(self.path).path).strip('/').split('/')
            if not parts or not re.fullmatch(r'[a-f0-9]{12}',parts[0]):self.send_error(404);return
            original=OUTPUT/parts[0]
            base=original.resolve()
            if original.is_symlink() or not base.is_relative_to(OUTPUT.resolve()):self.send_error(404);return
            target=(base/'/'.join(parts[1:])).resolve()
            if target.is_dir():target=target/'index.html'
            if not target.is_relative_to(base) or not target.is_file() or any(p.startswith('.') for p in target.relative_to(base).parts):self.send_error(404);return
            raw=target.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type',mimetypes.guess_type(str(target))[0] or 'application/octet-stream')
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-cache')
            self.send_header('X-Content-Type-Options','nosniff')
            # A separate origin keeps generated JS away from the dashboard's API/IndexedDB.
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'self'")
            self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(('127.0.0.1',port),Preview)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return server
