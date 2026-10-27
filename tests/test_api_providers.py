import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from backend.api_providers import ApiAdapter, validate
from backend.core import Store, Supervisor
from backend.policy import choose


class ApiTests(unittest.TestCase):
    def config(self, **values):
        return dict({'id':'api-test','name':'Test','protocol':'openai','base_url':'http://127.0.0.1:11434/v1','model':'local'}, **values)

    def test_reject_credentials_and_nonlocal_http(self):
        for change in [{'api_key':'secret'}, {'base_url':'http://example.com'}, {'base_url':'https://user:pass@example.com'}, {'key_env':'secret-value'}, {'protocol':'tess'}]:
            with self.assertRaises(ValueError):
                validate(self.config(**change))

    def test_local_http_contract(self):
        seen=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                seen.append((self.path, self.headers.get('Authorization'), json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                raw=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'ok'}}], 'usage':{'prompt_tokens':5,'completion_tokens':1}}).encode()
                self.send_response(200);self.end_headers();self.wfile.write(raw)
            def log_message(self,*args): pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with patch.dict(os.environ, {'TEST_MODEL_KEY':'private-key'}):
                adapter=ApiAdapter(self.config(base_url='http://127.0.0.1:'+str(server.server_port)+'/v1',key_env='TEST_MODEL_KEY'))
                self.assertEqual(adapter.probe()['state'],'validation_required')
                events=[]
                result=adapter.execute('hello','.',lambda *args:events.append(args),threading.Event())
                self.assertEqual(result['status'],'completed')
                self.assertEqual(result['usage'],{'input_tokens':5,'output_tokens':1})
                self.assertEqual(seen[0],('/v1/chat/completions','Bearer private-key',{'messages':[{'role':'user','content':'hello'}],'model':'local','stream':False}))
                self.assertNotIn('private-key',json.dumps(adapter.probe()))
                self.assertEqual(adapter.probe()['state'],'available')
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_tess_poll_and_cancel(self):
        adapter=ApiAdapter(self.config(protocol='tess',base_url='https://api.tess.im',key_env='TESS_API_KEY',workspace_id='1',agent_id='2'))
        with patch.object(adapter,'http',side_effect=[{'responses':[{'id':3,'status':'starting'}]}, {'id':3,'status':'succeeded','output':'done'}]) as http:
            result=adapter.execute('hello','.',lambda *a:None,threading.Event())
            self.assertEqual(result['result'],'done')
            self.assertEqual(http.call_args_list[0].args[0],'/agents/2/execute')
            self.assertEqual(http.call_args_list[0].args[1]['tools'],'no-tools')
            self.assertEqual(http.call_args_list[1].args[0],'/agent-responses/3')
        cancel=threading.Event();cancel.set()
        with patch.object(adapter,'http') as http:
            self.assertEqual(adapter.execute('x','.',lambda *a:None,cancel)['status'],'cancelled')
            http.assert_not_called()

    def test_partial_result_and_error_redaction(self):
        adapter=ApiAdapter(self.config())
        with patch.object(adapter,'http',return_value={'choices':[{'finish_reason':'length','message':{'content':'partial'}}]}):
            self.assertEqual(adapter.execute('x','.',lambda *a:self.fail('partial emitted'),threading.Event())['status'],'failed')
        from urllib.error import HTTPError
        for code,state in [(401,'authentication_required'),(429,'rate_limited'),(500,'failed')]:
            with patch.object(adapter,'http',side_effect=HTTPError('https://secret',code,'private-key',{},None)):
                result=adapter.execute('x','.',lambda *a:None,threading.Event())
                self.assertEqual(result['status'],state)
                self.assertNotIn('private-key',json.dumps(result))

    def test_api_connections_are_disabled_in_supervisor(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder+'/test.sqlite',folder)
            supervisor=Supervisor(store)
            with self.assertRaises(ValueError):supervisor.save_provider(self.config())
            with self.assertRaises(ValueError):store.create('hello','local','api-test','one')
            self.assertFalse(any(p['id'].startswith('api-') for p in supervisor.providers()))

    def test_tess_api_configured_and_executed_in_supervisor(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {'TESS_API_KEY': '3114152|secret'}):
                store = Store(folder + '/test.sqlite', folder)
                supervisor = Supervisor(store)
                self.assertIn('tess', supervisor.adapters)
                supervisor.adapters['tess'].state = 'available'
                task_id = store.create('resumo da tarefa', 'local', 'tess', 'tess-test-key')
                self.assertEqual(store.task(task_id)['provider'], 'tess')
                with patch.object(supervisor.adapters['tess'], 'http', side_effect=[
                    {'responses': [{'id': 99, 'status': 'starting'}]},
                    {'id': 99, 'status': 'succeeded', 'output': 'RESPOSTA_TESS_OK'}
                ]):
                    supervisor.run_once()
                self.assertEqual(store.task(task_id)['status'], 'completed')
                self.assertEqual(store.task(task_id)['result'], 'RESPOSTA_TESS_OK')
                self.assertEqual(supervisor.adapters['tess'].state, 'available')

if __name__=='__main__':unittest.main()

