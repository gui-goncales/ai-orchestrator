"""Integration contract for BusinessWork HTTP and persisted AI results."""
import base64
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from backend.business_work_http import BusinessWorkHTTP
from backend.core import Store, Supervisor
import threading
from backend.web_providers import WebAdapter, DEFAULT_CHATGPT


class FakeAdapter:
    def __init__(self):
        self.calls = 0
    def probe(self):
        return {'id':'codex','state':'available','installed':True}
    def chat_turn(self, messages, cancel, deadline):
        self.calls += 1
        assert 'Conteúdo de referência' in messages[0]['content']
        return '{"blocks":[{"type":"heading","level":2,"text":"Visão geral"},{"type":"paragraph","text":"Texto criado por IA para o cliente. [Fonte 1]"},{"type":"bullet","text":"Informação extraída da referência. [Fonte 1]"}]}', {}


def supervisor_for(db):
    supervisor = Supervisor(Store(db, str(Path(db).parent)), FakeAdapter())
    supervisor.providers = lambda: [{'id':'codex','state':'available','installed':True},
                                    {'id':'web-chatgpt','state':'available','installed':True}]
    return supervisor


class BusinessWorkHTTPIntegration(unittest.TestCase):
    def test_full_flow_persists_and_exports_selected_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / 'work.sqlite3')
            supervisor = supervisor_for(db)
            http = BusinessWorkHTTP(db, supervisor)
            client = http.post('/api/business/contexts', {'name': 'Cliente de Teste'})
            cid = client['id']
            self.assertEqual(len(http.get('/api/business/contexts')), 1)
            source = http.post('/api/business/contexts/'+cid+'/sources', {'name': 'notas.txt', 'data': base64.b64encode('Conteúdo de referência'.encode()).decode()})
            sources = http.get('/api/business/contexts/'+cid+'/sources')
            self.assertEqual(len(sources), 1)
            version_id = sources[0]['version_id']
            generated = http.post('/api/business/contexts/'+cid+'/generate', {'kind': 'briefing', 'title': 'Briefing Teste', 'source_version_ids': [version_id], 'provider_id': 'codex'})
            self.assertEqual(generated['status'], 'queued')
            self.assertEqual(supervisor.adapter.calls, 0)
            self.assertEqual(supervisor.store.task(generated['task_id'])['provider'], 'auto')
            self.assertTrue(supervisor.run_once())
            self.assertEqual(supervisor.store.task(generated['task_id'])['provider'], 'codex')
            generated = http.get('/api/business/contexts/'+cid+'/generations')[0]
            self.assertEqual(generated['status'], 'completed')
            self.assertEqual(supervisor.adapter.calls, 1)
            docid = generated['deliverable_id']
            document = http.get('/api/business/documents/'+docid)
            first = document['versions'][0]
            block = next(b for b in first['content'] if 'Texto criado' in b['text'])
            edited = http.post('/api/business/documents/'+docid+'/edit', {'expected_version_id': first['id'], 'block_id': block['id'], 'text': 'Trecho revisado e editável.'})
            reopened = BusinessWorkHTTP(db, supervisor)
            saved = reopened.get('/api/business/documents/'+docid)
            self.assertEqual(len(saved['versions']), 2)
            self.assertEqual(len(reopened.get('/api/business/contexts/'+cid+'/sources')), 1)
            self.assertEqual(len(reopened.get('/api/business/contexts/'+cid+'/generations')), 1)
            first_export = reopened.get('/api/business/documents/'+docid+'/export?version_id='+first['id'])
            last_export = reopened.get('/api/business/documents/'+docid+'/export?version_id='+saved['versions'][-1]['id'])
            self.assertEqual(first_export[0], 'docx')
            with zipfile.ZipFile(io.BytesIO(first_export[1][1])) as z:
                self.assertIn(b'Texto criado por IA', z.read('word/document.xml'))
            with zipfile.ZipFile(io.BytesIO(last_export[1][1])) as z:
                xml = z.read('word/document.xml')
                self.assertIn(b'Trecho revisado e edit', xml)
                self.assertNotIn(b'Texto criado por IA', xml)


class QueuedGenerationTests(unittest.TestCase):
    def setup_work(self, folder):
        db = str(Path(folder)/'work.sqlite3')
        sup = supervisor_for(db)
        http = BusinessWorkHTTP(db, sup)
        cid = http.work.create_context('A')['id']
        src = http.work.add_source(cid, 'notes.txt', 'Conteúdo de referência'.encode())
        return db, sup, http, cid, {'kind':'briefing','title':'Teste',
                                  'source_version_ids':[src['version_id']], 'provider_id':'codex'}

    def test_chatgpt_uses_queue_and_documents_finalize_once(self):
        with tempfile.TemporaryDirectory() as folder:
            db, sup, http, cid, body = self.setup_work(folder)
            class Browser(WebAdapter):
                def __init__(self):
                    super().__init__(DEFAULT_CHATGPT)
                    self.calls = 0
                def execute(self, prompt, cwd, event, cancel, timeout=120):
                    self.calls += 1
                    text, usage = FakeAdapter().chat_turn([{'content':prompt}], cancel, 0)
                    event('message', {'text':text})
                    return {'status':'completed','result':text,'usage':usage}
            browser = Browser()
            sup.adapters['web-chatgpt'] = browser
            sup.providers = lambda: [{'id':'web-chatgpt','state':'available','installed':True,'automatic_routing':True}]
            body.pop('provider_id')
            queued = http.generate(cid, body)
            self.assertEqual(queued['status'],'queued')
            self.assertEqual(browser.calls,0)
            self.assertTrue(sup.run_once())
            for _ in range(3):
                self.assertEqual(http.get('/api/business/contexts/'+cid+'/generations')[0]['status'],'completed')
            self.assertEqual(browser.calls,1)
            self.assertEqual(len(http.work.documents(cid)),1)
            with sup.store.connect() as conn:
                self.assertGreater(conn.execute('SELECT COUNT(*) FROM checkpoints WHERE task_id=?',(queued['task_id'],)).fetchone()[0],0)

    def test_restart_recovers_interrupted_task_then_explicit_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            db, sup, http, cid, body = self.setup_work(folder)
            queued = http.generate(cid, body)
            sup.store.update(queued['task_id'],'running')
            reopened = supervisor_for(db)
            reopened.store.recover()
            controller = BusinessWorkHTTP(db, reopened)
            generation = controller.get('/api/business/contexts/'+cid+'/generations')[0]
            self.assertEqual(generation['status'],'interrupted')
            self.assertEqual(reopened.adapter.calls,0)
            controller.post('/api/business/generations/'+queued['id']+'/resume',{})
            self.assertTrue(reopened.run_once())
            self.assertEqual(controller.get('/api/business/contexts/'+cid+'/generations')[0]['status'],'completed')

    def test_legacy_provider_override_cannot_bypass_automatic_routing(self):
        with tempfile.TemporaryDirectory() as folder:
            db, sup, http, cid, body = self.setup_work(folder)
            body['provider_id']='rea'
            queued = http.generate(cid, body)
            self.assertEqual(sup.store.task(queued['task_id'])['provider'], 'auto')
            self.assertTrue(sup.run_once())
            self.assertEqual(sup.store.task(queued['task_id'])['provider'], 'codex')

    def test_no_eligible_provider_rejected_before_creating_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            db, sup, http, cid, body = self.setup_work(folder)
            sup.providers = lambda: [{'id':'rea','state':'available','installed':True}]
            with self.assertRaises(ValueError):
                http.generate(cid, body)
            self.assertEqual(http.work.generations(cid), [])

    def test_cancelled_queued_generation_does_not_call_model(self):
        with tempfile.TemporaryDirectory() as folder:
            db, sup, http, cid, body = self.setup_work(folder)
            queued = http.generate(cid, body)
            result = http.post('/api/business/generations/'+queued['id']+'/cancel',{})
            self.assertEqual(result['status'],'cancelled')
            self.assertFalse(sup.run_once())
            self.assertEqual(sup.adapter.calls,0)
            self.assertEqual(http.work.documents(cid),[])

    def test_lost_attachment_is_reconciled_without_new_task(self):
        with tempfile.TemporaryDirectory() as folder:
            db, sup, http, cid, body = self.setup_work(folder)
            queued = http.generate(cid, body)
            with http.work.session() as conn:
                conn.execute('UPDATE business_generations SET task_id=NULL WHERE id=?',(queued['id'],))
            restored = http.get('/api/business/contexts/'+cid+'/generations')[0]
            self.assertEqual(restored['task_id'],queued['task_id'])
            with sup.store.connect() as conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0],1)


if __name__ == '__main__':
    unittest.main()
