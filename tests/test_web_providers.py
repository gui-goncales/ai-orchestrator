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
            result=adapter.execute('hello','.',lambda kind, data:self.assertEqual(kind, 'browser_round'),threading.Event())
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

    def test_capture_failure_is_not_retried_and_diagnostics_are_preserved(self):
        from backend.agent_engine import run_universal_agent
        adapter = WebAdapter(DEFAULT_CHATGPT)
        events = []
        with tempfile.TemporaryDirectory() as folder, patch.object(adapter, 'command', return_value={
                'status': 'interrupted', 'result': '', 'submitted': True,
                'reason': 'capture_timeout', 'error': 'Captura não confirmada'}) as command:
            result = run_universal_agent(adapter, 'Inspecione.', folder,
                lambda k, d: events.append((k, d)), threading.Event())
        self.assertEqual(result['status'], 'interrupted')
        self.assertEqual(command.call_count, 1)
        self.assertFalse(any(k == 'tool_call' for k, _ in events))
        diagnostic = next(d for k, d in events if k == 'browser_round')
        self.assertEqual(diagnostic['reason'], 'capture_timeout')
        self.assertTrue(diagnostic['submitted'])
        self.assertGreater(diagnostic['input_bytes'], 0)

    def test_binding_is_retained_per_execution_and_reset_for_new_run(self):
        adapter = WebAdapter(DEFAULT_CHATGPT)
        adapter.begin_run()
        with patch.object(adapter, 'command', return_value={
                'status': 'completed', 'result': 'ok', 'context': {'url': 'fixture', 'count': 1}}):
            adapter.execute('fixture', '.', lambda *a: None, threading.Event())
        self.assertEqual(adapter.run_context.binding['count'], 1)
        adapter.begin_run()
        self.assertIsNone(adapter.run_context.binding)

    def test_local_failure_has_separate_diagnostic(self):
        adapter = WebAdapter(DEFAULT_CHATGPT)
        events = []
        with patch.object(adapter, 'command', side_effect=OSError('fixture')):
            result = adapter.execute('fixture', '.', lambda k, d: events.append((k, d)), threading.Event())
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(events[0][1]['reason'], 'local_transport_failed')
        self.assertIsNone(events[0][1]['submitted'])

    def test_execution_preempts_health_check_and_submits_once(self):
        adapter = WebAdapter(DEFAULT_CHATGPT)
        adapter.state = 'available'
        checking = threading.Event()
        calls = []
        checks = []
        events = []
        def command(action, cancel, *args):
            calls.append(action)
            if action == 'check':
                checking.set()
                self.assertTrue(cancel.wait(2))
                return {'status': 'cancelled', 'session_ready': False}
            return {'status': 'completed', 'result': 'fixture', 'submitted': True}
        with patch.object(adapter, 'command', side_effect=command):
            thread = threading.Thread(target=lambda: checks.append(adapter.check()))
            thread.start()
            self.assertTrue(checking.wait(1))
            result = adapter.execute('fixture', '.', lambda k, d: events.append((k, d)), threading.Event())
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(calls, ['check', 'execute'])
        self.assertEqual(checks[0]['reason'], 'health_check_preempted')
        self.assertEqual(adapter.state, 'available')
        self.assertFalse(adapter.operation.locked())
        self.assertEqual(sum(k == 'browser_submission' for k, _ in events), 1)
        self.assertEqual(next(d for k, d in events if k == 'browser_session_wait')['reason'], 'health_check_preempted')

    def test_waiting_execution_can_cancel_without_submitting(self):
        adapter = WebAdapter(DEFAULT_CHATGPT)
        checking, release, cancelled = threading.Event(), threading.Event(), threading.Event()
        result, calls = [], []
        def command(action, cancel, *args):
            calls.append(action)
            checking.set()
            release.wait(2)
            return {'session_ready': True, 'controls_mapped': True}
        with patch.object(adapter, 'command', side_effect=command):
            check = threading.Thread(target=adapter.check)
            check.start()
            self.assertTrue(checking.wait(1))
            check_cancel = adapter.check_cancel
            execute = threading.Thread(target=lambda: result.append(adapter.execute('fixture', '.', lambda *a: None, cancelled)))
            try:
                execute.start()
                self.assertTrue(check_cancel.wait(1))
                cancelled.set()
                execute.join(1)
                self.assertFalse(execute.is_alive())
                self.assertEqual(result[0]['status'], 'cancelled')
                self.assertEqual(calls, ['check'])
            finally:
                release.set()
                check.join(2)
                execute.join(2)

    def test_health_check_that_ignores_cancellation_has_bounded_wait(self):
        adapter = WebAdapter(DEFAULT_CHATGPT)
        checking, release = threading.Event(), threading.Event()
        events = []
        def command(action, cancel, *args):
            checking.set()
            release.wait(2)
            return {'session_ready': True}
        with patch.object(adapter, 'command', side_effect=command) as call:
            thread = threading.Thread(target=adapter.check)
            thread.start()
            self.assertTrue(checking.wait(1))
            try:
                result = adapter.execute('fixture', '.', lambda k, d: events.append((k, d)), threading.Event(), timeout=.05)
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(call.call_count, 1)
                self.assertEqual(events[-1][1]['reason'], 'local_lock_timeout')
                self.assertFalse(events[-1][1]['submitted'])
            finally:
                release.set()
                thread.join(2)

    def test_another_execution_is_never_preempted_or_duplicated(self):
        adapter = WebAdapter(DEFAULT_CHATGPT)
        started, release = threading.Event(), threading.Event()
        def command(*args):
            started.set()
            release.wait(2)
            return {'status': 'completed', 'result': 'fixture'}
        with patch.object(adapter, 'command', side_effect=command) as call:
            thread = threading.Thread(target=lambda: adapter.execute('first', '.', lambda *a: None, threading.Event()))
            thread.start()
            self.assertTrue(started.wait(1))
            try:
                events = []
                result = adapter.execute('second', '.', lambda k, d: events.append((k, d)), threading.Event())
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(call.call_count, 1)
                self.assertEqual(events[-1][1]['reason'], 'local_session_busy')
                self.assertFalse(events[-1][1]['submitted'])
            finally:
                release.set()
                thread.join(2)

    def test_refresh_stops_if_task_starts_between_provider_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            supervisor = Supervisor(Store(folder+'/db', folder))
            first, second = WebAdapter(DEFAULT_TESS), WebAdapter(DEFAULT_CHATGPT)
            supervisor.adapters = {'web-tess': first, 'web-chatgpt': second}
            with patch.object(first, 'check', side_effect=lambda: setattr(supervisor, 'active', 'fixture')), patch.object(second, 'check') as check:
                supervisor.refresh_connections()
            check.assert_not_called()

    def test_extension_protocol_is_required_before_marking_controls_ready(self):
        adapter = WebAdapter({**DEFAULT_CHATGPT, 'extension_id': 'a'*32})
        with patch.object(adapter, 'command', return_value={'status': 'validation_required', 'session_ready': True, 'controls_mapped': True}):
            result = adapter.check()
        self.assertEqual(result['reason'], 'extension_upgrade_required')
        self.assertEqual(adapter.state, 'validation_required')
        self.assertFalse(adapter.controls_mapped)
        with patch.object(adapter, 'command', return_value={'status': 'validation_required', 'session_ready': True, 'controls_mapped': True, 'bridge_protocol': 2, 'worker_version': '0.2.0', 'capture_mode': 'async_poll'}):
            adapter.check()
        self.assertEqual(adapter.state, 'available')

    def test_transport_phase_and_capture_id_are_logged_without_prompt(self):
        adapter = WebAdapter(DEFAULT_CHATGPT)
        events = []
        with patch.object(adapter, 'command', return_value={'status': 'interrupted', 'result': '',
                'reason': 'extension_channel_timeout', 'submitted': None, 'channel_phase': 'start',
                'bridge_protocol': 2, 'worker_version': '0.2.0', 'poll_count': 0, 'job_id': 'fixture-id'}):
            adapter.execute('private fixture prompt', '.', lambda k, d: events.append((k, d)), threading.Event())
        diagnostic = next(d for k, d in events if k == 'browser_round')
        self.assertEqual(diagnostic['channel_phase'], 'start')
        self.assertEqual(diagnostic['job_id'], 'fixture-id')
        self.assertEqual(diagnostic['bridge_protocol'], 2)
        self.assertNotIn('private fixture prompt', str(diagnostic))
