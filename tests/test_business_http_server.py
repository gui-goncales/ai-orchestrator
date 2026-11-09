"""Exercise the actual HTTP server and queue using an isolated fake model."""
import base64
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
import zipfile


SCRIPT = '''
import sys
from backend.core import Supervisor
from backend.server import serve
class Model:
 def probe(self): return {'id':'codex','installed':True,'state':'available'}
 def chat_turn(self,messages,cancel,deadline):
  return '{"blocks":[{"type":"heading","text":"Resumo"},{"type":"paragraph","text":"Original HTTP [Fonte 1]"},{"type":"bullet","text":"A confirmar: prazo"}]}',{}
Supervisor.providers=lambda self: [self.adapter.probe()]
Supervisor.refresh_connections=lambda self: None
serve(port=int(sys.argv[1]),data=sys.argv[2],adapter=Model())
'''


class BusinessRealHTTPTests(unittest.TestCase):
    def test_http_queue_edit_export_and_server_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            origin = 'http://127.0.0.1:' + str(port)
            db = str(Path(folder)/'http.sqlite3')
            process = None

            def request(path, body=None, binary=False):
                data = None if body is None else json.dumps(body).encode()
                req = urllib.request.Request(origin+path, data=data,
                    headers={'Origin':origin, 'Content-Type':'application/json'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    raw = response.read()
                    return raw if binary else json.loads(raw)

            def start():
                proc = subprocess.Popen([sys.executable,'-c',SCRIPT,str(port),db],
                    cwd=str(Path(__file__).resolve().parents[1]),
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                deadline = time.monotonic()+15
                while time.monotonic()<deadline:
                    if proc.poll() is not None:
                        self.fail(proc.stderr.read().decode())
                    try:
                        request('/api/health')
                        return proc
                    except OSError:
                        time.sleep(.05)
                proc.terminate(); proc.wait(timeout=10);proc.stderr.close()
                self.fail('Temporary server failed to start')

            def stop(proc):
                proc.terminate()
                try: proc.wait(timeout=10)
                except subprocess.TimeoutExpired: proc.kill();proc.wait(timeout=5)
                proc.stderr.close()

            try:
                process = start()
                self.assertEqual(request('/api/business/providers')[0]['id'],'codex')
                for name in ('a','b'):
                    (Path(folder)/name).mkdir()
                    request('/api/workspace/folders',{'id':name,'name':'Folder '+name,'path':str(Path(folder)/name)})
                bindings = request('/api/workspace/folders')
                self.assertEqual(len({b['project_id'] for b in bindings}),2)
                self.assertEqual({Path(b['path']).name for b in bindings},{'a','b'})
                cid = request('/api/business/contexts', {'name':'HTTP Client'})['id']
                source = request('/api/business/contexts/'+cid+'/sources', {
                    'name':'notes.txt','data':base64.b64encode(b'Authorized reference').decode()})
                queued = request('/api/business/contexts/'+cid+'/generate', {
                    'kind':'briefing','title':'HTTP delivery','provider_id':'codex',
                    'source_version_ids':[source['version_id']]})
                self.assertIn(queued['status'],('queued','running'))
                deadline = time.monotonic()+10
                while time.monotonic()<deadline:
                    generation = request('/api/business/contexts/'+cid+'/generations')[0]
                    if generation['status']=='completed':break
                    time.sleep(.05)
                self.assertEqual(generation['status'],'completed',generation)
                docid = generation['deliverable_id']
                document = request('/api/business/documents/'+docid)
                first = document['versions'][0]
                block = next(b for b in first['content'] if 'Original HTTP' in b['text'])
                edited = request('/api/business/documents/'+docid+'/edit', {
                    'expected_version_id':first['id'],'block_id':block['id'],'text':'Edited HTTP'})
                stop(process);process=None
                process = start()
                restored = request('/api/business/documents/'+docid)
                self.assertEqual(len(restored['versions']),2)
                self.assertEqual(request('/api/workspace/folders'),bindings)
                self.assertEqual(restored['current_version_id'],edited['version_id'])
                for version, expected in ((first['id'],b'Original HTTP'),(edited['version_id'],b'Edited HTTP')):
                    raw = request('/api/business/documents/'+docid+'/export?version_id='+version,binary=True)
                    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                        self.assertIn(expected,archive.read('word/document.xml'))
                self.assertEqual(len(request('/api/business/contexts/'+cid+'/documents')),1)
            finally:
                if process is not None:stop(process)
