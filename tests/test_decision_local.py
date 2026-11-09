import math
import os
import unittest
from unittest.mock import patch

from backend.decision import Choice, Decision, Noul, Score


class LocalDecisionTests(unittest.TestCase):
    def test_inferred_intent_cannot_grant_permissions(self):
        inferred = Decision.classify_mode('Implemente um filtro')
        self.assertEqual(inferred['selected_mode'], 'work')
        self.assertEqual(inferred['permitted_operations'], ['read'])
        self.assertTrue(inferred['permission_conflict'])
        explicit = Decision.classify_mode('Implemente um filtro', authorization={'read_files': True, 'write_files': True, 'run_commands': True})
        self.assertFalse(explicit['permission_conflict'])
        self.assertEqual(explicit['authorization_source'], 'explicit_grants')

    def test_authorization_schema_is_strict(self):
        for authorization in [True, [], {'read_files': 'true'}, {'unknown': True}]:
            with self.subTest(authorization=authorization), self.assertRaises(ValueError):
                Decision.classify_mode('Analise', authorization=authorization)

    def test_unknown_answers_explicitly_abstain(self):
        result = Decision.decide('irrelevant', {'c': Choice('Quem?', ['a', 'b']), 'n': Noul('É seguro?')}, force_local=True)
        self.assertFalse(result.usable('c'))
        self.assertFalse(result.usable('n'))
        self.assertFalse(result.usable('missing'))
        self.assertEqual(result.nouls['n'].noul, 0.5)
        self.assertEqual(result.nouls['n'].confidence, 0)

    def test_shadow_retains_authoritative_result(self):
        scorer = lambda state, questions: {'q': {'a': 10, 'b': -10}}
        with patch('backend.decision_runtime.configured_scorer', return_value=('shadow', scorer)):
            result = Decision.decide('state', {'q': Choice('Qual?', ['a', 'b'])})
        self.assertEqual(result.engine_used, 'local-heuristic')
        self.assertFalse(result.usable('q'))
        self.assertEqual(result.shadow['engine'], 'local-scorer')

    def test_shadow_failure_does_not_expose_state(self):
        def failing(*args):
            raise RuntimeError('private state')
        with patch('backend.decision_runtime.configured_scorer', return_value=('shadow', failing)):
            result = Decision.decide('private state', {'q': Noul('Qual?')})
        self.assertEqual(result.shadow, {'status': 'unavailable', 'error_type': 'RuntimeError'})

    def test_active_semantic_mode_cannot_expand_grants(self):
        scorer = lambda state, questions: {'mode': {'analyze': -10, 'plan': -10, 'artifact': -10, 'work': 10}}
        with patch.dict(os.environ, {'DECISION_MODE': 'on'}), patch('backend.decision_runtime.configured_scorer', return_value=('on', scorer)):
            result = Decision.classify_mode('Veja isto', authorization={'read_files': True})
        self.assertEqual(result['selected_mode'], 'work')
        self.assertTrue(result['permission_conflict'])
        self.assertEqual(result['permitted_operations'], ['read'])

    def test_active_semantic_uncertainty_blocks_task(self):
        scorer = lambda state, questions: {'mode': {'analyze': 0, 'plan': 0, 'artifact': 0, 'work': 0}}
        with patch.dict(os.environ, {'DECISION_MODE': 'on'}), patch('backend.decision_runtime.configured_scorer', return_value=('on', scorer)):
            result = Decision.classify_mode('Veja isto')
        self.assertTrue(result['decision_blocked'])

    def test_negation_quotes_explanation_and_planning(self):
        cases = [
            ('Não corrija nada. Apenas explique o problema.', 'analyze'),
            ('Explique como refatorar o serviço.', 'analyze'),
            ('Do not modify the code. Explain how to fix it.', 'analyze'),
            ('Analise a frase "implemente o módulo".', 'analyze'),
            ('Prepare um plano para refatorar o serviço.', 'plan'),
            ('Planeje a migração e depois implemente o adaptador.', 'work'),
            ('Analise. Se a solução for segura, aplique a correção.', 'work'),
            ('Crie um relatório PDF sem modificar o código.', 'artifact'),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(Decision.classify_mode(text)['selected_mode'], expected)

    def test_credentials_never_enable_network(self):
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'not-a-secret', 'JEV_API_KEY': 'not-a-secret'}), patch('urllib.request.urlopen', side_effect=AssertionError('network forbidden')):
            self.assertEqual(Decision.decide('x', {'q': Noul('Pergunta?')}).engine_used, 'local-heuristic')

    def test_no_evidence_is_not_confidence(self):
        r = Decision.decide('xyz', {'c': Choice('Escolha', ['a', 'b']), 's': Score('Risco?', ['baixo', 'alto'])})
        self.assertEqual(r.choices['c'].confidence, 0)
        self.assertEqual(r.scores['s'].confidence, 0)
        self.assertFalse(r.to_dict()['calibrated'])

    def test_local_logits_contract_and_question_semantics(self):
        questions = {'yes': Noul('Está autorizado?'), 'no': Noul('Está proibido?'), 's': Score('Risco?', ['baixo', 'alto']), 'c': Choice('Escolha', {'a': 'primeira', 'b': 'segunda'})}
        def scorer(state, specs):
            self.assertEqual(state, {'authorized': True})
            self.assertEqual(specs['yes']['instructions'], 'Está autorizado?')
            self.assertEqual(specs['s']['criteria'], ['baixo', 'alto'])
            return {'yes': {'false': -1000, 'true': 1000}, 'no': {'false': 1000, 'true': -1000}, 's': {'0': 0, '1': 0}, 'c': {'a': 0, 'b': math.log(3)}}
        r = Decision.decide({'authorized': True}, questions, scorer=scorer)
        self.assertEqual(r.engine_used, 'local-scorer')
        self.assertEqual(r.nouls['yes'].noul, 1)
        self.assertEqual(r.nouls['no'].noul, 0)
        self.assertEqual(r.scores['s'].score, 0.5)
        self.assertEqual(r.scores['s'].confidence, 0)
        self.assertAlmostEqual(r.choices['c'].probabilities['b'], 0.75)
        self.assertEqual(r.choices['c'].choice, 'b')

    def test_malformed_model_output_is_rejected_without_hidden_fallback(self):
        for result in [{}, {'q': {'a': 0}}, {'q': {'a': float('nan'), 'b': 0}}, {'q': {'a': True, 'b': 0}}, {'q': {'a': 0, 'b': 0}, 'extra': {}}]:
            with self.subTest(result=result), self.assertRaises(ValueError):
                Decision.decide('state', {'q': Choice('Escolha', ['a', 'b'])}, scorer=lambda *_: result)

    def test_invalid_questions_are_rejected(self):
        for create in [lambda: Choice('x', ['a', 'a']), lambda: Choice('x', [1]), lambda: Score('x', ['a', 'a']), lambda: Noul(''), lambda: Decision.decide('x', {})]:
            with self.assertRaises(ValueError):
                create()

    def test_failover_requires_fault_and_positive_gates(self):
        providers = [{'id': 'antigravity', 'installed': True, 'state': 'available'}]
        self.assertIsNone(Decision.decide_failover({}, 'codex', 'invalid configuration', providers))
        negative = Decision.decide('x', {
            'selected_substitute': Choice('Escolha', ['antigravity']),
            'should_failover': Noul('Permitir?'),
            'is_quota_or_service_fault': Noul('Cota?'),
            'continuity_feasibility': Score('Continuidade?', ['bad', 'medium', 'good'])})
        negative.nouls['should_failover'].noul = 0.1
        negative.engine_used = 'local-scorer'
        with patch.object(Decision, 'decide', return_value=negative):
            self.assertIsNone(Decision.decide_failover({}, 'codex', 'usage limit', providers))

    def test_failover_rejects_out_of_set_substitute(self):
        providers = [{'id': 'antigravity', 'installed': True, 'state': 'available'}]
        real = Decision.decide
        def invalid(state, questions):
            r = real(state, questions)
            r.choices['selected_substitute'].choice = 'unknown'
            r.engine_used = 'local-scorer'
            return r
        with patch.object(Decision, 'decide', side_effect=invalid):
            self.assertIsNone(Decision.decide_failover({}, 'codex', 'usage limit', providers))
