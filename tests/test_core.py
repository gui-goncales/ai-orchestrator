import json
import tempfile
import threading
import unittest
from pathlib import Path
from backend.core import Store, Supervisor, classify_error, handoff


class Fake:
    def __init__(self, status='completed'):
        self.status = status
        self.calls = []
    def probe(self):
        return {'id': 'codex', 'state': 'available', 'installed': True}
    def execute(self, prompt, cwd, emit, cancel):
        self.calls.append(prompt)
        emit('message', {'text': 'Resultado confirmado'})
        emit('usage', {'input_tokens': 10, 'output_tokens': 2})
        return {'status': self.status, 'result': 'Resultado confirmado', 'usage': {'input_tokens': 10, 'output_tokens': 2}, 'error': None if self.status == 'completed' else 'Falha simulada'}


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root/'db.sqlite', self.root)
    def tearDown(self):
        self.tmp.cleanup()
    def create(self, key='key'):
        return self.store.create('Analisar requisitos essenciais sem perder restrições', 'local', 'auto', key)
    def test_idempotent_creation(self):
        self.assertEqual(self.create(), self.create())
        self.assertEqual(len(self.store.snapshot()['tasks']), 1)
    def test_invalid_provider(self):
        with self.assertRaises(ValueError):
            self.store.create('X', 'local', 'invalid', 'key')
    def test_invalid_project(self):
        with self.assertRaises(ValueError):
            self.store.create('X', 'missing', 'auto', 'key')
    def test_execution_checkpoints_usage(self):
        id = self.create()
        s = Supervisor(self.store, Fake())
        self.assertTrue(s.run_once())
        self.assertEqual(self.store.task(id)['status'], 'completed')
        self.assertEqual(len(self.store.snapshot()['checkpoints']), 2)
        self.assertEqual(json.loads(self.store.task(id)['usage'])['input_tokens'], 10)
    def test_resume_after_restart(self):
        id = self.create()
        self.store.update(id, 'running', result='Etapa confirmada')
        reopened = Store(self.root/'db.sqlite', self.root)
        reopened.recover()
        self.assertEqual(reopened.task(id)['status'], 'interrupted')
        f = Fake()
        s = Supervisor(reopened, f)
        s.resume(id)
        s.run_once()
        self.assertIn('Etapa confirmada', f.calls[0])
    def test_cancel_queued_never_executes(self):
        id = self.create()
        f = Fake()
        s = Supervisor(self.store, f)
        s.cancel(id)
        self.assertFalse(s.run_once())
        self.assertEqual(f.calls, [])
    def test_cancel_running_wins_race(self):
        id = self.create()
        s = Supervisor(self.store, Fake())
        self.store.update(id, 'running')
        s.cancel(id)
        self.store.update(id, 'completed', result='late')
        self.assertEqual(self.store.task(id)['status'], 'cancelled')
    def test_no_completed_rerun(self):
        id = self.create()
        s = Supervisor(self.store, Fake())
        s.run_once()
        with self.assertRaises(ValueError):
            s.resume(id)
    def test_rate_limit_stops_without_alternate(self):
        id = self.create()
        s = Supervisor(self.store, Fake('rate_limited'))
        s.run_once()
        self.assertEqual(self.store.task(id)['status'], 'rate_limited')
        self.assertFalse(s.run_once())
    def test_explicit_errors_only(self):
        self.assertEqual(classify_error({'code': 'usage_limit_reached'}), 'rate_limited')
        self.assertEqual(classify_error({'message': 'rate limit in quoted document'}), 'failed')
        self.assertEqual(classify_error({'code': 'unauthorized'}), 'authentication_required')
    def test_handoff_preserves_objective(self):
        id = self.create()
        t = self.store.task(id)
        packet = handoff(t)
        self.assertEqual(packet['version'], 1)
        self.assertEqual(packet['objective'], t['objective'])
        self.assertTrue(packet['constraints'])
    def test_checkpoint_failure_rolls_back_state(self):
        id = self.create()
        def fail(*args):
            raise RuntimeError('Simulated disk failure')
        self.store.checkpoint = fail
        with self.assertRaises(RuntimeError):
            self.store.update(id, 'running')
        self.assertEqual(self.store.task(id)['status'], 'queued')
    def test_memory_deduplicated_not_silently_cut(self):
        id = self.create()
        with self.store.connect() as db:
            db.execute('INSERT INTO memory(id,project_id,content,time) VALUES(?,?,?,?)', ('a', 'local', 'Preservar requisito XYZ', 'now'))
            db.execute('INSERT INTO memory(id,project_id,content,time) VALUES(?,?,?,?)', ('b', 'local', 'Preservar requisito XYZ', 'now'))
        f = Fake()
        Supervisor(self.store, f).run_once()
        self.assertEqual(f.calls[0].count('Preservar requisito XYZ'), 1)
    def test_retry_accumulates_reported_usage(self):
        id = self.create()
        s = Supervisor(self.store, Fake('failed'))
        s.run_once()
        s.resume(id)
        s.adapter = Fake()
        s.run_once()
        self.assertEqual(json.loads(self.store.task(id)['usage'])['input_tokens'], 20)
    def test_serial_execution(self):
        self.create()
        s = Supervisor(self.store, Fake())
        s.active = 'other'
        self.assertFalse(s.run_once())


if __name__ == '__main__':
    unittest.main()
