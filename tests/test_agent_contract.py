import json
from pathlib import Path
import tempfile
import threading
import unittest

from backend.agent_contract import worker_contract, worker_prompt
from backend.agent_engine import AgentRunner, WorkspaceTools
from backend.core import Store
from backend.policy import build_context, choose
from backend.decision import Decision


def action(name, **args):
    return '<tool_call name="' + name + '">' + json.dumps(args) + '</tool_call>'


class AgentContractTests(unittest.TestCase):
    def test_prompt_advertises_only_runtime_capabilities(self):
        with tempfile.TemporaryDirectory() as root:
            reader = WorkspaceTools(root, read_only=True)
            prompt = worker_prompt(reader)
            for name in ['write_file', 'delete_file', 'edit_file', 'run_command']:
                self.assertNotIn('<tool_call name="' + name + '">', prompt)
            self.assertIn('<tool_call name="read_file">', prompt)
            writer = WorkspaceTools(root, commands_allowed=False)
            prompt = worker_prompt(writer)
            self.assertIn('<tool_call name="write_file">', prompt)
            self.assertNotIn('<tool_call name="run_command">', prompt)
            self.assertNotIn('run_command', worker_contract(writer)['tools'])

    def test_resume_refreshes_prompt_and_denies_pending_write(self):
        with tempfile.TemporaryDirectory() as root:
            store = Store(Path(root) / 'state.sqlite', root)
            work = Path(root) / 'work'
            work.mkdir()
            task_id = store.create('Analise o projeto', 'local', 'auto', 'resume-contract', workflow='work')
            cancel = threading.Event()
            events = []
            def emit(kind, payload):
                events.append((kind, payload))
                if kind == 'tool_result' and payload['name'] == 'list_dir':
                    cancel.set()
            first = AgentRunner(WorkspaceTools(str(work))).run(
                lambda *_: (action('list_dir', path='.') + action('write_file', path='blocked.txt', content='must not exist'), {}),
                'Analise o projeto', emit, cancel, store=store, task_id=task_id)
            self.assertEqual(first['status'], 'cancelled')
            seen = []
            def resume_model(messages, *args):
                seen.extend(messages)
                return action('finish', summary='Análise entregue; escrita bloqueada pelo contrato.'), {}
            second = AgentRunner(WorkspaceTools(str(work), read_only=True)).run(
                resume_model, 'Analise o projeto', lambda kind, payload: events.append((kind, payload)), threading.Event(), store=store, task_id=task_id)
            self.assertEqual(second['status'], 'completed')
            self.assertFalse((work / 'blocked.txt').exists())
            self.assertNotIn('<tool_call name="write_file">', seen[0]['content'])
            self.assertTrue(any(kind == 'agent_contract_refreshed' for kind, _ in events))
            saved = store.load_execution_state(task_id)
            self.assertTrue(saved['worker_contract']['read_only'])
            denied = [p['result'] for kind, p in events if kind == 'tool_result' and p['name'] == 'write_file']
            self.assertTrue(denied and 'error' in denied[0])

    def test_context_constraints_follow_decision_instead_of_workflow_name(self):
        task = {'objective': 'Gere um relatório', 'workflow': 'deliver', 'spec': {
            'mode_decision': Decision.classify_mode('Gere um relatório', 'artifact')}}
        prompt, _ = build_context(task, [])
        packet = json.loads(prompt.split('Dados da tarefa:\n', 1)[1])
        self.assertTrue(packet['execution_plan']['write_allowed'])
        self.assertTrue(any('Escrita autorizada' in c for c in packet['constraints']))
        self.assertTrue(any('comandos não autorizada' in c for c in packet['constraints']))

    def test_initial_routing_and_failover_share_blocked_flag(self):
        providers = [{'id': 'antigravity', 'installed': True, 'state': 'available', 'automatic_routing_blocked': True}]
        task = {'id': 'current', 'objective': 'Analise o código'}
        self.assertIsNone(choose(task, providers, [])[0])
        self.assertIsNone(Decision.decide_failover(task, 'codex', 'usage limit', providers))

    def test_ready_and_static_tools_have_consistent_eligibility(self):
        providers = [
            {'id': 'codex', 'installed': True, 'state': 'ready'},
            {'id': 'rea', 'installed': True, 'state': 'available', 'automatic_routing': True},
        ]
        task = {'id': 'current', 'objective': 'Analise o código'}
        self.assertEqual(choose(task, providers, [])[0], 'codex')
        self.assertIsNone(Decision.decide_failover(task, 'codex', 'usage limit', providers))
