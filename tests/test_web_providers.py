import tempfile
import threading
import unittest
from unittest.mock import patch
from backend.core import Store, Supervisor
from backend.web_providers import WebAdapter, DEFAULT_TESS, DEFAULT_CHATGPT, validate
from backend.policy import choose


class WebProviderTests(unittest.TestCase):
    def test_chatgpt_is_available_as_independent_browser_connection(self):
        with tempfile.TemporaryDirectory() as folder:
            supervisor = Supervisor(Store(folder+'/db', folder))
            adapter = supervisor.adapters['web-chatgpt']
            self.assertIsInstance(adapter, WebAdapter)
            self.assertEqual(adapter.config['chat_url'], 'https://chatgpt.com')
            self.assertNotEqual(adapter.id, 'codex')
            self.assertEqual(adapter.state, 'authentication_required')

    def test_chatgpt_defaults_upgrade_empty_selectors_and_lock_origin(self):
        config = {**DEFAULT_CHATGPT, 'input_selector': '', 'response_selector': '', 'busy_selector': ''}
        validated = validate(config)
        self.assertIn('data-composer-markdown', validated['input_selector'])
        self.assertIn('assistant-message', validated['response_selector'])
        with self.assertRaises(ValueError):
            validate({**config, 'login_url': 'https://example.com', 'chat_url': 'https://example.com'})

    def test_validation(self):
        self.assertEqual(validate(DEFAULT_TESS)['id'],'web-tess')
        for changes in ({'id':'../escape'},{'login_url':'https://user:pass@tess.im/login'},
                        {'login_url':'https://tess.im/login?token=secret'}, {'chat_url':'https://evil.example/chat'},
                        {'key_env':'SECRET'}, {'input_selector':['textarea']}):
            with self.assertRaises(ValueError):validate(dict(DEFAULT_TESS,**changes))

    def test_registry_restart_and_no_api_route(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder+'/db',folder);supervisor=Supervisor(store)
            config=dict(DEFAULT_TESS,input_selector='#prompt',response_selector='.assistant',busy_selector='#stop')
            supervisor.save_provider(config)
            restarted=Supervisor(store)
            self.assertEqual(restarted.adapters['web-tess'].config,config)
            task_id=store.create('hello','local','web-tess','one')
            self.assertIsNone(choose(store.task(task_id),[restarted.adapters['web-tess'].probe()],[])[0])
            restarted.adapters['web-tess'].state='available'
            with patch.object(restarted.adapters['web-tess'],'command',return_value={'status':'completed','result':'SESSION_OK','usage':{},'submitted':True}):
                restarted.run_once()
            self.assertEqual(store.task(task_id)['status'],'completed')
            self.assertEqual(choose(store.task(task_id),[restarted.adapters['web-tess'].probe()],[])[0],'web-tess')
            self.assertTrue(store.create('build','local','web-tess','two','deliver'))

    def test_check_never_claims_inference_success(self):
        adapter=WebAdapter(DEFAULT_TESS)
        with patch.object(adapter,'command',return_value={'session_ready':True}):
            adapter.check()
        self.assertEqual(adapter.probe()['state'],'validation_required')
        self.assertFalse(adapter.probe()['execution_validated'])
        with patch.object(adapter,'command',return_value={'status':'authentication_required','result':'','usage':{},'error':'login'}):
            result=adapter.execute('hello','.',lambda *a:self.fail('No message expected'),threading.Event())
        self.assertEqual(result['status'],'authentication_required')

    def test_check_preserves_validated_session_and_identical_save(self):
        with tempfile.TemporaryDirectory() as folder:
            supervisor=Supervisor(Store(folder+'/db',folder))
            adapter=supervisor.adapters['web-tess'];adapter.state='available'
            supervisor.save_provider(dict(DEFAULT_TESS))
            self.assertIs(adapter,supervisor.adapters['web-tess'])
            with patch.object(adapter,'command',return_value={'session_ready':True,'controls_mapped':True}):adapter.check()
            self.assertEqual(adapter.state,'available')
            with patch.object(adapter,'command',return_value={'session_ready':False}):adapter.check()
            self.assertEqual(adapter.state,'authentication_required')

    def test_live_session_with_controls_is_usable_without_generation(self):
        adapter=WebAdapter(DEFAULT_TESS)
        with patch.object(adapter,'command',return_value={'session_ready':True,'controls_mapped':True}):result=adapter.check()
        self.assertEqual(result['state'],'available')
        self.assertFalse(result['execution_validated'])
        with patch.object(adapter,'command',return_value={'session_ready':False,'reason':'conversation_missing','status':'session_closed'}):adapter.check()
        self.assertEqual(adapter.probe()['state'],'session_closed')

    def test_closed_browser_metadata_is_not_written_as_task_columns(self):
        adapter=WebAdapter(DEFAULT_TESS)
        with patch.object(adapter,'command',return_value={'status':'session_closed','reason':'browser_unavailable','session_ready':False,'controls_mapped':False}):
            result=adapter.execute('x','.',lambda *a:None,threading.Event())
        self.assertEqual(set(result),{'status','result','usage','error'})

    def test_refresh_after_backend_restart_checks_live_sessions(self):
        with tempfile.TemporaryDirectory() as folder:
            supervisor=Supervisor(Store(folder+'/db',folder))
            web=supervisor.adapters['web-tess'];google=supervisor.adapters['antigravity']
            with patch.object(web,'command',return_value={'session_ready':True,'controls_mapped':True}), patch.object(google,'check_auth') as check:
                supervisor.refresh_connections()
            self.assertEqual(web.state,'available');check.assert_called_once()
            supervisor.active='task'
            with patch.object(web,'check') as check:supervisor.refresh_connections()
            check.assert_not_called()

    def test_occupied_session(self):
        adapter=WebAdapter(DEFAULT_TESS);adapter.operation.acquire()
        try:
            with self.assertRaises(ValueError):adapter.open_login()
            self.assertEqual(adapter.execute('x','.',lambda *a:None,threading.Event())['status'],'failed')
        finally:adapter.operation.release()
