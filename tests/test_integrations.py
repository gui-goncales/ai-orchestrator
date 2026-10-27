import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
from backend.core import Store, Supervisor
from backend.integrations import ReaAdapter, GeminiAdapter, AntigravityAdapter
from test_core import Fake

class IntegrationTests(unittest.TestCase):
    def test_antigravity_account_check_uses_official_catalog_without_generation(self):
        adapter=AntigravityAdapter()
        with patch.object(adapter,'path',return_value='/tool/agy'), patch('backend.integrations.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='gemini-test\tGemini Test\n',stderr='PRIVATE')) as run:
            state=adapter.check_auth()
        self.assertEqual(state['state'],'available');self.assertTrue(state['session_ready'])
        self.assertFalse(state['execution_validated'])
        self.assertEqual(run.call_args.args[0],['/tool/agy','models'])
        self.assertNotIn('PRIVATE',json.dumps(state))
        with patch.object(adapter,'path',return_value='/tool/agy'), patch('backend.integrations.subprocess.run',return_value=SimpleNamespace(returncode=1,stdout='',stderr='PRIVATE')):
            state=adapter.check_auth()
        self.assertFalse(state['session_ready']);self.assertNotEqual(state['state'],'available')
        self.assertNotIn('PRIVATE',json.dumps(state))

    def test_catalog_does_not_clear_execution_failure_automatically(self):
        adapter = AntigravityAdapter()
        adapter.state = 'failed'
        adapter.connection_error = 'Antigravity: ERROR'
        with patch.object(adapter, 'path', return_value='/tool/agy'), patch(
                'backend.integrations.subprocess.run', return_value=SimpleNamespace(
                    returncode=0, stdout='gemini-test\tGemini Test\n', stderr='')):
            self.assertEqual(adapter.check_auth()['state'], 'failed')
            self.assertEqual(adapter.check_auth(explicit=True)['state'], 'available')

    def test_antigravity_reports_success_and_usage(self):
        value={'status':'SUCCESS','response':'OK','usage':{'input_tokens':7,'output_tokens':3,'thinking_tokens':2,'total_tokens':10,'cache_read_tokens':4}}
        parsed=AntigravityAdapter.parse(json.dumps(value),0)
        self.assertEqual(parsed['status'],'completed')
        self.assertEqual(parsed['usage']['cached_input_tokens'],4)
        self.assertEqual(parsed['usage']['output_tokens'],3)
    def test_antigravity_failure_never_marked_complete(self):
        self.assertEqual(AntigravityAdapter.parse('{"status":"ERROR","response":"partial"}',1)['status'],'failed')
        self.assertEqual(AntigravityAdapter.parse('not authenticated',1)['status'],'authentication_required')
    def test_gemini_usage_is_reported_not_estimated(self):
        r=GeminiAdapter.parse(json.dumps({'response':'ok','stats':{'models':{'model':{'tokens':{'input':12,'candidates':3,'cached':5}}}}}),0)
        self.assertEqual(r['usage'],{'input_tokens':12,'output_tokens':3,'cached_input_tokens':5})
        self.assertEqual(r['status'],'completed')
    def test_gemini_no_usage_is_unknown(self):
        self.assertEqual(GeminiAdapter.parse('{"response":"ok"}',0)['usage'],{})
    def test_gemini_invalid_json_fails(self):
        self.assertEqual(GeminiAdapter.parse('unexpected',0)['status'],'failed')
    def test_rea_rejects_outside_project_and_unknown_command(self):
        with tempfile.TemporaryDirectory() as root:
            for spec in [{'kind':'shell','target':'.'},{'kind':'javascript','target':'/private/tmp'}]:
                with self.assertRaises(ValueError):ReaAdapter.target(spec,root)
    def test_rea_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root,'escape').symlink_to('/private/tmp')
            with self.assertRaises(ValueError):ReaAdapter.target({'kind':'javascript','target':'escape'},root)
    def test_rea_stages_persist_and_do_not_repeat(self):
        with tempfile.TemporaryDirectory() as root:
            store=Store(Path(root)/'db',root)
            id=store.create('Pesquisar objetivo','local','codex','rea-test','rea')
            fake=Fake('failed');s=Supervisor(store,fake)
            with store.connect() as db:
                db.execute('INSERT INTO task_steps VALUES(?,?,?,?)',(id,'research','Evidência confirmada','now'))
            s.run_once()
            self.assertEqual(len(fake.calls),1)
            self.assertIn('EVALUATE:',fake.calls[0])
            self.assertIn('Evidência confirmada',fake.calls[0])
            s.resume(id);s.adapter=Fake();s.run_once()
            self.assertEqual(len(s.adapter.calls),2)
            stages=store.snapshot()['task_steps']
            self.assertEqual({r['stage'] for r in stages},{'research','evaluate','architect'})
            self.assertEqual(store.task(id)['status'],'completed')
    def test_old_database_migrates_without_losing_task(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'db'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE tasks(id TEXT PRIMARY KEY,project_id TEXT,objective TEXT,provider TEXT,status TEXT,result TEXT,usage TEXT,error TEXT,created_at TEXT,updated_at TEXT)')
                db.execute("INSERT INTO tasks VALUES('old','local','Preservar','codex','completed','ok','{}',NULL,'now','now')")
            store=Store(path,root)
            self.assertEqual(store.task('old')['workflow'],'direct')
            self.assertEqual(store.task('old')['result'],'ok')

class RecoveryProtocolTests(unittest.TestCase):
    def test_empty_success_has_actionable_error_not_success_label(self):
        parsed=AntigravityAdapter.parse('{"status":"SUCCESS","response":"","usage":{"input_tokens":10}}',0)
        self.assertEqual(parsed['status'],'failed')
        self.assertIn('sem resposta pública',parsed['error'])
        self.assertEqual(parsed['usage']['input_tokens'],10)
    def test_public_stream_recovers_empty_final_without_internal_reasoning(self):
        events=[{'event':'step_update','step_update':{'step_type':'thinking','text_delta':'PRIVATE_DO_NOT_EXPOSE'}},
                {'event':'step_update','step_update':{'step_type':'agent_response','text_delta':'Resposta '}},
                {'event':'step_update','step_update':{'step_type':'agent_response','text_delta':'pública'}},
                {'event':'result','result':{'status':'SUCCESS','response':'','usage':{'input_tokens':3}}}]
        parsed,diag=AntigravityAdapter.parse_stream('\n'.join(json.dumps(e) for e in events),0)
        self.assertEqual(parsed['result'],'Resposta pública')
        self.assertEqual(parsed['status'],'completed')
        self.assertNotIn('PRIVATE',json.dumps(parsed)+json.dumps(diag))
    def test_final_response_is_authoritative_and_not_duplicated(self):
        events=[{'event':'step_update','step_update':{'step_type':'agent_response','text_delta':'ok'}},
                {'event':'result','result':{'status':'SUCCESS','response':'ok'}}]
        parsed,_=AntigravityAdapter.parse_stream('\n'.join(json.dumps(e) for e in events),0)
        self.assertEqual(parsed['result'],'ok')
    def test_missing_result_is_not_false_completion(self):
        parsed,_=AntigravityAdapter.parse_stream('{"event":"init"}',0)
        self.assertEqual(parsed['status'],'failed')

class ReadOnlyFallbackTests(unittest.TestCase):
    def test_empty_google_stage_continues_with_codex_without_repeating_confirmed_stage(self):
        class EmptyGoogle(Fake):
            def execute(self,prompt,cwd,emit,cancel):
                self.calls.append(prompt)
                return {'status':'failed','result':'','usage':{'input_tokens':5},'error':'Antigravity encerrou com SUCCESS, mas sem resposta pública.'}
        with tempfile.TemporaryDirectory() as root:
            store=Store(Path(root)/'db',root);id=store.create('Pesquisar arquitetura','local','antigravity','fallback','rea')
            with store.connect() as db:db.execute('INSERT INTO task_steps VALUES(?,?,?,?)',(id,'research','Pesquisa confirmada','now'))
            codex=Fake();google=EmptyGoogle();s=Supervisor(store,codex);s.adapters['antigravity']=google;s.providers=lambda:[{'id':'codex','installed':True,'state':'available'},{'id':'antigravity','installed':True,'state':'available'}];s.run_once()
            self.assertEqual(len(google.calls),1);self.assertEqual(len(codex.calls),2)
            self.assertIn('EVALUATE:',codex.calls[0]);self.assertIn('Pesquisa confirmada',codex.calls[0])
            self.assertEqual(store.task(id)['status'],'completed');self.assertEqual(store.task(id)['provider'],'codex')
            self.assertEqual(json.loads(store.task(id)['usage'])['input_tokens'],25)
    def test_structured_public_report_is_valid_response(self):
        parsed=AntigravityAdapter.parse(json.dumps({'status':'SUCCESS','response':'','structured_output':{'report':'Relatório público'}}),0)
        self.assertEqual(parsed['result'],'Relatório público');self.assertEqual(parsed['status'],'completed')

class ResumeRecoveryTests(unittest.TestCase):
    def test_resume_switches_after_recorded_empty_success_without_recalling_google(self):
        with tempfile.TemporaryDirectory() as root:
            store=Store(Path(root)/'db',root);id=store.create('Planejar objetivo','local','antigravity','resume-repair','rea')
            store.update(id,'failed',error='Antigravity encerrou com SUCCESS, mas sem resposta pública.')
            s=Supervisor(store,Fake());s.resume(id)
            self.assertEqual(store.task(id)['provider'],'codex')
            self.assertEqual(store.task(id)['status'],'queued')
            self.assertTrue(any(e['kind']=='rea_stage_provider_changed' for e in store.snapshot()['events']))
