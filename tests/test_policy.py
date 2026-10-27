import json
import tempfile
import unittest
from pathlib import Path
from backend.policy import choose,build_context,validate_output
from backend.core import Store,Supervisor
from test_core import Fake

class PolicyTests(unittest.TestCase):
    def task(self):
        return {'id':'current','objective':'Analisar documento do projeto','provider':'auto','result':'','error':None}
    def providers(self):
        return [{'id':'codex','installed':True,'state':'available'},{'id':'antigravity','installed':True,'state':'authentication_required'},{'id':'rea','installed':True,'state':'available'}]
    def test_decision_preserves_analysis_intent_and_permissions(self):
        task = self.task()
        task['objective'] = 'Após uma análise aprofundada do Decision, diga se funciona e como melhorar.'
        prompt, _ = build_context(task, [])
        packet = json.loads(prompt.split('Dados da tarefa:\n', 1)[1])
        self.assertEqual(packet['objective'], task['objective'])
        self.assertEqual(packet['execution_plan']['mode'], 'analysis')
        self.assertFalse(packet['execution_plan']['write_allowed'])
        self.assertIn('diagnóstico', packet['execution_plan']['completion'])

    def test_decision_does_not_take_intent_from_reference(self):
        from backend.decision import Decision
        plan = Decision.plan_task({'objective': 'Responda OK', 'workflow': 'work'})
        self.assertEqual(plan['mode'], 'execute')
        self.assertTrue(plan['write_allowed'])
        self.assertEqual(plan['objective'], 'Responda OK')

    def test_auto_command_request_selects_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp)/'db', tmp)
            task_id = store.create('Execute python3 -m unittest discover -s tests -v',
                                   'local', 'codex', 'run-tests', workflow='auto')
            self.assertEqual(store.task(task_id)['workflow'], 'work')

    def test_conversation_groups_existing_turns_and_deletes_whole_thread(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp)/'db', tmp)
            first = store.create('Primeiro pedido', 'local', 'codex', 'first')
            store.update(first, 'completed', result='Resposta inicial')
            second = store.create('Continue', 'local', 'codex', 'second', spec={'conversation_parent': first})
            store.update(second, 'completed', result='Segunda resposta')
            third = store.create('Mais detalhes', 'local', 'codex', 'third', spec={'conversation_parent': second})
            other = store.create('Outra conversa', 'local', 'codex', 'other')
            tasks = {t['id']: t for t in store.snapshot()['tasks']}
            self.assertEqual({tasks[i]['conversation_id'] for i in (first, second, third)}, {first})
            self.assertEqual(len(tasks[third]['conversation_history']), 2)
            with self.assertRaises(ValueError): store.delete_conversation(first)
            store.update(third, 'cancelled')
            result = store.delete_conversation(second)
            self.assertEqual(set(result['deleted_ids']), {first, second, third})
            self.assertEqual([t['id'] for t in store.snapshot()['tasks']], [other])
            with store.connect() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM commands WHERE task_id=?', (second,)).fetchone()[0], 0)

    def test_first_contact_is_an_analysis_task(self):
        from backend.decision import Decision
        plan = Decision.plan_task({'objective': 'Atue como engenheiro de software sênior tendo contato pela primeira vez com esse projeto: /tmp/project/'})
        self.assertEqual(plan['mode'], 'analysis')
        self.assertIn('reconhecimento técnico', ' '.join(plan['instructions']))
        self.assertFalse(plan['write_allowed'])

    def test_continue_resolves_last_substantive_request(self):
        from backend.decision import Decision
        plan = Decision.plan_task({'objective': 'Continue', 'spec': {'conversation_history': [
            {'objective': 'Analise o Decision e sugira melhorias', 'result': 'Parcial'},
            {'objective': 'Continue', 'result': 'Parcial'}]}})
        self.assertEqual(plan['active_objective'], 'Analise o Decision e sugira melhorias')
        self.assertEqual(plan['mode'], 'analysis')
        self.assertEqual(plan['objective'], 'Continue')

    def test_followup_receives_runtime_evidence_even_when_summary_is_pronto(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp)/'db', tmp)
            first = store.create('Melhore o Decision', 'local', 'codex', 'evidence-first', workflow='work')
            store.update(first, 'completed', result='Pronto')
            with store.connect() as db:
                store.event(db, first, 'tool_result', {'name': 'edit_file', 'result': {'status': 'ok', 'path': 'backend/agent_engine.py'}})
                store.event(db, first, 'tool_result', {'name': 'run_command', 'result': {'status': 'failed', 'exit_code': 1, 'command': ['python3', '-m', 'unittest']}})
            second = store.create('Me explique o que foi feito', 'local', 'codex', 'evidence-second', spec={'conversation_parent': first})
            packet = json.loads(store.task(second)['spec'])
            evidence = packet['conversation_history'][-1]['execution_evidence']
            self.assertEqual(evidence['files_changed'][0]['path'], 'backend/agent_engine.py')
            self.assertEqual(evidence['commands'][0]['exit_code'], 1)
            prompt, _ = build_context(store.task(second), [])
            self.assertIn('runtime_tool_results', prompt)

    def test_failed_agent_is_excluded_despite_available_catalog(self):
        history = [{'id': 'old', 'provider': 'antigravity', 'status': 'failed', 'objective': 'Analisar documento'}]
        providers = [dict(p, state='available') for p in self.providers()[:2]]
        selected, decision = choose(self.task(), providers, history)
        self.assertEqual(selected, 'codex')
        self.assertTrue(any(p['provider'] == 'antigravity' for p in decision['excluded']))

    def test_explicit_unavailable_agent_is_blocked_without_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp)/'db', tmp)
            task_id = store.create('Analise', 'local', 'codex', 'unavailable-explicit')
            fake = Fake()
            supervisor = Supervisor(store, fake)
            supervisor.providers = lambda: [{'id': 'codex', 'installed': True, 'state': 'offline'}]
            supervisor.run_once()
            self.assertEqual(store.task(task_id)['status'], 'blocked')
            self.assertEqual(fake.calls, [])

    def test_failover_does_not_retry_agent_blocked_by_recent_failure(self):
        from backend.decision import Decision
        providers = [{'id': 'antigravity', 'installed': True, 'state': 'available', 'automatic_routing_blocked': True}]
        self.assertIsNone(Decision.decide_failover(self.task(), 'codex', 'usage limit', providers))

    def test_google_previous_success_cannot_override_current_unavailability(self):
        past=[{'id':'old','provider':'antigravity','objective':'Analisar documento','status':'completed','quality':'unreviewed','usage':{}}]
        selected,decision=choose(self.task(),self.providers(),past)
        self.assertEqual(selected,'codex')
        self.assertFalse(decision['uses_llm_for_routing'])
    def test_later_auth_or_rate_error_excludes_provider(self):
        for state in ('authentication_required','rate_limited'):
            past=[{'id':'old','provider':'antigravity','status':state,'objective':'Analisar documento'}]
            selected,_=choose(self.task(),self.providers(),past)
            self.assertEqual(selected,'codex')
    def test_no_agent_blocks_without_provider_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'db',tmp);id=store.create('A','local','auto','key')
            fake=Fake();s=Supervisor(store,fake)
            s.providers=lambda:[{'id':'codex','installed':False,'state':'offline'}]
            self.assertTrue(s.run_once());self.assertEqual(fake.calls,[])
            self.assertEqual(store.task(id)['status'],'blocked')
    def test_auto_persists_decision_and_calls_only_one_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'db',tmp);id=store.create('A','local','auto','key')
            fake=Fake();s=Supervisor(store,fake);s.providers=lambda:[self.providers()[0]]
            s.run_once();t=store.task(id)
            self.assertEqual(t['requested_provider'],'auto');self.assertEqual(t['provider'],'codex')
            self.assertEqual(len(fake.calls),1);self.assertTrue(json.loads(t['routing'])['reason'])
    def test_exact_validation_failure_requires_review_without_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'db',tmp);id=store.create('Diga OK','local','codex','key',spec={'expected_output':'OK'})
            fake=Fake();Supervisor(store,fake).run_once()
            self.assertEqual(store.task(id)['status'],'needs_review')
            self.assertEqual(len(fake.calls),1)
    def test_all_critical_memory_survives_even_without_keyword_match(self):
        task=self.task();task['objective']='Preservar exatamente:\n  codigo = "a b"'
        memory=[{'id':'critical','content':'Nunca excluir dados de clientes','kind':'constraint'}]
        prompt,metrics=build_context(task,memory)
        self.assertIn('Nunca excluir dados de clientes',prompt)
        self.assertTrue(metrics['objective_preserved']);self.assertTrue(metrics['constraints_preserved'])
        self.assertEqual(metrics['references_omitted'],[])
    def test_only_optional_irrelevant_references_omitted(self):
        memories=[{'id':'x','content':'História de um assunto sem relação','kind':'reference'},{'id':'y','content':'Documento do projeto com decisões','kind':'reference'}]
        prompt,metrics=build_context(self.task(),memories)
        self.assertEqual(metrics['references_selected'],['y']);self.assertEqual(metrics['references_omitted'],['x'])
        self.assertNotIn('História de um assunto',prompt)
    def test_dedup_and_budget_never_truncate_constraints(self):
        memories=[{'id':'a','content':'X'*81000,'kind':'constraint'}]
        with self.assertRaises(ValueError):build_context(self.task(),memories)
        prompt,metrics=build_context(self.task(),[{'id':'a','content':'Obrigatório'},{'id':'b','content':'Obrigatório'}])
        self.assertEqual(prompt.count('Obrigatório'),1);self.assertEqual(metrics['duplicates_removed'],['b'])
    def test_reference_duplicate_never_displaces_mandatory_constraint(self):
        memories=[{'id':'ref','content':'Regra crítica','kind':'reference'},{'id':'rule','content':'Regra crítica','kind':'constraint'}]
        prompt,metrics=build_context(self.task(),memories)
        self.assertIn('Regra crítica',prompt)
        self.assertEqual(metrics['duplicates_removed'],['ref'])
    def test_simple_request_has_no_operational_report_instruction(self):
        task=self.task();task['objective']='Responda exatamente OK'
        prompt,_=build_context(task,[])
        self.assertNotIn('Indique pendências e evidências',prompt)
        self.assertEqual(prompt.count(task['objective']),1)
        self.assertEqual(validate_output('OK\n',{'expected_output':'OK'})['status'],'passed')
    def test_usage_routing_requires_accepted_samples_for_all_agents(self):
        providers=[dict(p,state='available') for p in self.providers()[:2]]
        history=[]
        for provider,tokens in [('codex',100),('antigravity',50)]:
            for i in range(3):history.append({'id':provider+str(i),'provider':provider,'objective':self.task()['objective'],'status':'completed','quality':'accepted','usage':{'input_tokens':tokens,'output_tokens':1}})
        selected,decision=choose(self.task(),providers,history)
        self.assertEqual(selected,'antigravity')
        self.assertIn('amostras aceitas',decision['reason'])

    def test_decision_primitives_typesafe_jev(self):
        from backend.decision import Decision, Choice, Score, Noul
        state = "Implementar componente de busca com debounce em TypeScript e testes unitários."
        questions = {
            "needs_code": Noul("Exige escrita ou geração de código?"),
            "complexity": Score("Qual o nível de esforço técnico?", ["baixo", "médio", "alto"]),
            "preferred_service": Choice("Qual o melhor provedor?", ["codex", "antigravity", "rea"])
        }
        res = Decision.decide(state, questions, force_local=True)
        self.assertIn("needs_code", res.nouls)
        self.assertGreater(res.nouls["needs_code"].noul, 0.5)
        self.assertIn("complexity", res.scores)
        self.assertTrue(0.0 <= res.scores["complexity"].score <= 2.0)
        self.assertIn("preferred_service", res.choices)
        self.assertIn(res.choices["preferred_service"].choice, ["codex", "antigravity", "rea"])
        self.assertEqual(res.engine_used, "local-calibrated")

    def test_decision_failover_when_usage_limit_hit(self):
        from backend.decision import Decision
        task = self.task()
        failed_err = "You've hit your usage limit. Upgrade to Pro, visit https://chatgpt.com/settings/usage"
        providers = [
            {'id': 'codex', 'installed': True, 'state': 'rate_limited', 'auth': 'ChatGPT'},
            {'id': 'antigravity', 'installed': True, 'state': 'available', 'auth': 'Google · Gemini'}
        ]
        failover = Decision.decide_failover(task, 'codex', failed_err, providers)
        self.assertIsNotNone(failover)
        self.assertEqual(failover['selected_provider'], 'antigravity')
        self.assertIn("Alternância automática", failover['reason'])
        self.assertGreater(failover['confidence'], 0.0)

    def test_supervisor_automatic_failover_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp)/'db', tmp)
            id = store.create('Analisar arquitetura', 'local', 'codex', 'failover-key')
            fake_codex = Fake('rate_limited')
            fake_antigravity = Fake('completed')
            s = Supervisor(store, fake_codex)
            s.adapters['antigravity'] = fake_antigravity
            s.providers = lambda: [
                {'id': 'codex', 'installed': True, 'state': 'available'},
                {'id': 'antigravity', 'installed': True, 'state': 'available'}
            ]
            s.run_once()
            t = store.task(id)
            self.assertEqual(t['status'], 'completed')
            self.assertEqual(t['provider'], 'antigravity')
            self.assertIn('Resultado confirmado', t['result'])
            events = [e['kind'] for e in store.snapshot()['events']]
            self.assertIn('provider_failover', events)
