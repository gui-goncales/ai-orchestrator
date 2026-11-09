"""Local scoring boundary. A caller supplies in-process logits, never JSON text.

This module performs no network access, model downloads, or credential lookup.
Softmax distributions and entropy confidence are not calibrated correctness.
"""
import math


def score_questions(state, questions, scorer):
    from backend.decision import Choice, Score, ChoiceResult, ScoreResult, NoulResult, DecisionResult

    specs = {}
    for name, q in questions.items():
        kind = 'choice' if isinstance(q, Choice) else 'score' if isinstance(q, Score) else 'noul'
        options = list(q.criteria) if kind == 'choice' else [str(i) for i in range(len(q.criteria))] if kind == 'score' else ['false', 'true']
        specs[name] = {'type': kind, 'instructions': q.instructions,
                       'criteria': dict(q.criteria) if kind == 'choice' else list(q.criteria) if kind == 'score' else None,
                       'options': options}
    logits = scorer(state, specs)
    if not isinstance(logits, dict) or set(logits) != set(specs):
        raise ValueError('O avaliador local deve responder exatamente às perguntas fornecidas')
    result = DecisionResult()
    result.engine_used = 'local-scorer'
    result.reason = 'Distribuições derivadas de logits locais; calibração não demonstrada.'
    for name, spec in specs.items():
        values = logits[name]
        if not isinstance(values, dict) or set(values) != set(spec['options']):
            raise ValueError('Opções inválidas na resposta local: ' + name)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values.values()):
            raise ValueError('Logits devem ser números finitos: ' + name)
        maximum = max(values.values())
        weights = {k: math.exp(v - maximum) for k, v in values.items()}
        total = sum(weights.values())
        probabilities = {k: v / total for k, v in weights.items()}
        entropy = -sum(p * math.log(p) for p in probabilities.values() if p > 0)
        confidence = max(0.0, min(1.0, 1 - entropy / math.log(len(values)))) if len(values) > 1 else 1.0
        if spec['type'] == 'choice':
            result.choices[name] = ChoiceResult(max(probabilities, key=probabilities.get), probabilities, confidence)
        elif spec['type'] == 'score':
            score = sum(int(k) * p for k, p in probabilities.items())
            result.scores[name] = ScoreResult(score, probabilities, confidence)
        else:
            probability = probabilities['true']
            result.nouls[name] = NoulResult(probability, abs(probability - 0.5) * 2)
            confidence = abs(probability - 0.5) * 2
        if confidence < 0.2:
            result.abstentions[name] = 'Distribuição ambígua; confiança abaixo de 0,2 (limiar experimental)'
    return result
