import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from backend.decision_runtime import LocalProcessScorer
from backend.agent_engine import WorkspaceTools


class DecisionRuntimeTests(unittest.TestCase):
    def test_supervisor_blocks_abstained_task_before_provider_call(self):
        from backend.core import Store, Supervisor
        with tempfile.TemporaryDirectory() as root:
            store = Store(Path(root) / 'db.sqlite', root)
            task_id = store.create('Analise', 'local', 'codex', 'abstention-test')
            task = store.task(task_id)
            spec = json.loads(task['spec'])
            spec['mode_decision']['decision_blocked'] = True
            with store.connect() as db:
                db.execute('UPDATE tasks SET spec=? WHERE id=?', (json.dumps(spec), task_id))
            adapter = unittest.mock.Mock()
            supervisor = Supervisor(store, adapter)
            self.assertTrue(supervisor.run_once())
            self.assertEqual(store.task(task_id)['status'], 'blocked')
            adapter.execute.assert_not_called()

    def test_virtualenv_interpreter_symlink_is_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root / 'base').write_text('placeholder')
            (root / 'venv-python').symlink_to(root / 'base')
            scorer = LocalProcessScorer(root / 'venv-python', root)
            self.assertEqual(scorer.python_path, str(root / 'venv-python'))

    def test_write_permission_does_not_authorize_commands(self):
        with tempfile.TemporaryDirectory() as root:
            tools = WorkspaceTools(root, read_only=False, commands_allowed=False)
            tools.write_file('allowed.txt', 'written')
            self.assertEqual((Path(root) / 'allowed.txt').read_text(), 'written')
            with patch('backend.agent_engine.subprocess.Popen') as spawn, self.assertRaises(ValueError):
                tools.run_command(['python3', '-c', 'print(1)'])
            spawn.assert_not_called()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / 'python').write_text('placeholder')
        self.scorer = LocalProcessScorer(root / 'python', root)

    def test_bridge_uses_stdin_and_offline_environment(self):
        result = subprocess.CompletedProcess([], 0, json.dumps({'q': {'a': 1, 'b': 0}}), '')
        with patch('backend.decision_runtime.subprocess.run', return_value=result) as run:
            self.scorer('private state', {'q': {}})
        args, kwargs = run.call_args
        self.assertNotIn('private state', str(args))
        self.assertEqual(json.loads(kwargs['input'])['state'], 'private state')
        self.assertEqual(kwargs['env']['HF_HUB_OFFLINE'], '1')
        self.assertEqual(kwargs['env']['TRANSFORMERS_OFFLINE'], '1')
        self.assertNotIn('shell', kwargs)

    def test_bridge_errors_do_not_expose_stderr(self):
        result = subprocess.CompletedProcess([], 1, '', 'private state')
        with patch('backend.decision_runtime.subprocess.run', return_value=result), self.assertRaises(RuntimeError) as caught:
            self.scorer('private state', {})
        self.assertNotIn('private state', str(caught.exception))

    def test_input_budget_prevents_process_start(self):
        with patch('backend.decision_runtime.subprocess.run') as run, self.assertRaises(ValueError):
            self.scorer('x' * 70000, {})
        run.assert_not_called()

    def test_timeout_is_explicit(self):
        with patch('backend.decision_runtime.subprocess.run', side_effect=subprocess.TimeoutExpired([], 1)), self.assertRaises(RuntimeError):
            self.scorer('x', {})
