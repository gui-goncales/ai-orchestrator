"""Regression tests: batch interruption, journal replay and validation evidence."""
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from backend.agent_engine import AgentRunner, WorkspaceTools, run_universal_agent
from backend.core import Store

PROMPT = 'Implemente a correção e execute testes.'
OPEN = '<' + 'tool_call name="%s">'
CLOSE = '<' + '/tool_call>'


def call(name, **args):
    return OPEN % name + json.dumps(args) + CLOSE


class AgentResumeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name).resolve()
        self.work = base / 'work'
        self.work.mkdir()
        self.store = Store(base / 'state.sqlite', base)
        self.task_id = self.store.create('Testar retomada', 'local', 'auto', 'agent-resume')

    def tearDown(self):
        self.tmp.cleanup()

    def run_agent(self, model, cancel_on=None, events=None):
        cancel = threading.Event()
        events = events if events is not None else []

        def on_event(kind, payload):
            events.append((kind, payload))
            if cancel_on and kind == 'tool_result' and payload.get('name') == cancel_on:
                cancel.set()
        runner = AgentRunner(WorkspaceTools(str(self.work)))
        return runner.run(model, PROMPT, on_event, cancel, store=self.store, task_id=self.task_id)

    def first_batch(self, with_list_dir=False):
        parts = [call('write_file', path='fix.py', content='x=1'),
                 call('run_command', command=[sys.executable, '-c', 'print(1)'])]
        if with_list_dir:
            parts.append(call('list_dir', path='.'))
        parts.append(call('finish', summary='ok'))
        calls = []

        def model(messages, cancel, deadline):
            calls.append(1)
            return ''.join(parts), {}
        return model, calls

    @staticmethod
    def must_not_call(messages, cancel, deadline):
        raise AssertionError('o modelo não deveria ser chamado na retomada')

    def test_turn_budget_resumes_with_new_allowance_without_replaying_actions(self):
        events = []
        calls = []
        responses = [call('write_file', path='fix.py', content='x=1'),
                     call('run_command', command=[sys.executable, '-c', 'print(1)']),
                     call('finish', summary='Correção validada')]

        def model(messages, cancel, deadline):
            calls.append(len(messages))
            return responses[len(calls) - 1], {}

        def run():
            return AgentRunner(WorkspaceTools(str(self.work)), max_turns=1).run(
                model, PROMPT, lambda kind, payload: events.append((kind, payload)),
                threading.Event(), store=self.store, task_id=self.task_id)

        first = run()
        self.assertEqual(first['status'], 'interrupted')
        self.assertIn('Limite de rodadas', first['error'])
        self.assertEqual(self.store.load_execution_state(self.task_id)['turns'], 1)
        second = run()
        self.assertEqual(second['status'], 'interrupted')
        self.assertEqual(self.store.load_execution_state(self.task_id)['turns'], 2)
        final = run()
        self.assertEqual(final['status'], 'completed')
        self.assertEqual(self.store.load_execution_state(self.task_id)['turns'], 3)
        self.assertEqual(len(calls), 3)
        self.assertEqual(sum(k == 'execution_budget_exhausted' for k, _ in events), 2)
        with self.store.connect() as db:
            rows = dict(db.execute("SELECT tool_name,COUNT(*) FROM tool_actions WHERE task_id=? GROUP BY tool_name",
                                   (self.task_id,)))
        self.assertEqual(rows.get('write_file'), 1)
        self.assertEqual(rows.get('run_command'), 1)

    def test_browser_resume_transmits_only_latest_message_from_large_checkpoint(self):
        # Seed a durable checkpoint whose transcript exceeds the browser limit.
        AgentRunner(WorkspaceTools(str(self.work)), max_turns=1).run(
            lambda *args: (call('list_dir', path='.'), {}),
            'Analise o projeto.', lambda *args: None, threading.Event(),
            store=self.store, task_id=self.task_id)
        state = self.store.load_execution_state(self.task_id)
        state['messages'][0]['content'] = 'OLD_CONTEXT_' + 'x' * 200000
        state['messages'][-1]['content'] = 'Continue da última leitura confirmada.'
        self.store.save_execution_state(self.task_id, state)
        prompts, events = [], []

        class Browser:
            retains_conversation = True

            def execute(inner, prompt, cwd, on_event, cancel, timeout):
                prompts.append(prompt)
                return {'status': 'completed', 'result': 'Análise concluída.', 'usage': {}}

        result = run_universal_agent(Browser(), 'Analise o projeto.', str(self.work),
            lambda k, d: events.append((k, d)), threading.Event(),
            store=self.store, task_id=self.task_id)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(prompts), 1)
        self.assertIn('Continue da última leitura confirmada.', prompts[0])
        self.assertIn('Contrato atualizado na retomada', prompts[0])
        self.assertNotIn('OLD_CONTEXT_', prompts[0])
        self.assertTrue(next(d for k, d in events if k == 'model_input')['incremental'])
        self.assertNotIn('OLD_CONTEXT_', self.store.load_execution_state(self.task_id)['messages'][0]['content'])
        self.assertTrue(self.store.load_execution_state(self.task_id)['worker_contract']['read_only'])

    def test_supervisor_restores_prompt_before_context_budget_check(self):
        from unittest.mock import Mock, patch
        from backend.core import Supervisor
        self.store.update(self.task_id, 'cancelled')
        task_id = self.store.create('Continue o trabalho.', 'local', 'codex', 'large-resume', 'work')
        self.store.save_execution_state(task_id, {
            'messages': [{'role': 'system', 'content': 'tools'},
                         {'role': 'user', 'content': 'Original authorized request'},
                         {'role': 'assistant', 'content': 'previous'},
                         {'role': 'user', 'content': 'latest feedback'}]})
        self.store.update(task_id, 'running')
        self.store.update(task_id, 'failed', result='x' * 100000)
        adapter = Mock()
        adapter.probe.return_value = {'id': 'codex', 'installed': True, 'state': 'available'}
        supervisor = Supervisor(self.store, adapter)
        supervisor.resume(task_id)
        with patch('backend.core.build_context', side_effect=AssertionError('must not rebuild history')), \
             patch('backend.agent_engine.run_universal_agent', return_value={
                 'status': 'interrupted', 'result': '', 'usage': {}, 'error': 'paused'}) as run:
            self.assertTrue(supervisor.run_once())
        self.assertEqual(run.call_args.args[1], 'Original authorized request')
        self.assertEqual(run.call_args.kwargs['task_id'], task_id)

    def test_cancel_mid_batch_keeps_remaining_actions_and_resumes_without_model(self):
        model, calls = self.first_batch()
        result = self.run_agent(model, cancel_on='write_file')
        self.assertEqual(result['status'], 'cancelled')
        self.assertEqual(len(calls), 1)
        pending = self.store.load_execution_state(self.task_id)['pending_actions']
        self.assertIsNotNone(pending)
        self.assertEqual(pending['index'], 1)

        resumed = self.run_agent(self.must_not_call)
        self.assertEqual(resumed['status'], 'completed')
        self.assertIn('fix.py', resumed['files_mutated'])
        self.assertIn('"exit_code": 0', resumed['result'])
        with self.store.connect() as db:
            n = db.execute("SELECT COUNT(*) FROM tool_actions WHERE task_id=? AND tool_name='run_command' AND status='completed'",
                           (self.task_id,)).fetchone()[0]
        self.assertEqual(n, 1)

    def rewind_to_command(self):
        state = self.store.load_execution_state(self.task_id)
        state['pending_actions']['index'] = 1
        state['pending_actions']['observations'] = state['pending_actions']['observations'][:1]
        self.store.save_execution_state(self.task_id, state)

    def test_journal_replay_with_unchanged_files_keeps_validation(self):
        model, _ = self.first_batch(with_list_dir=True)
        first = self.run_agent(model, cancel_on='run_command')
        self.assertEqual(first['status'], 'cancelled')
        self.rewind_to_command()
        resumed = self.run_agent(self.must_not_call)
        self.assertEqual(resumed['status'], 'completed')

    def test_journal_replay_does_not_validate_files_changed_after_the_command(self):
        model, _ = self.first_batch(with_list_dir=True)
        first = self.run_agent(model, cancel_on='run_command')
        self.assertEqual(first['status'], 'cancelled')
        self.rewind_to_command()
        (self.work / 'fix.py').write_text('x=2')  # changed after the command really ran

        def model2(messages, cancel, deadline):
            return call('finish', summary='pronto'), {}
        events = []
        resumed = self.run_agent(model2, events=events)
        self.assertEqual(resumed['status'], 'failed')
        self.assertIn('Entrega não comprovada', resumed['error'])
        self.assertIn('validation_invalidated', [k for k, _ in events])


if __name__ == '__main__':
    unittest.main()
