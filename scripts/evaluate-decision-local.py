"""Offline semantic diagnostic; explicit model path and output, no API calls.

This hand-authored development set is not an independent calibration benchmark.
"""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.decision import Choice, Decision, Noul
from backend.decision_mlx import MlxScorer

CASES = [
    ('Explique a causa da falha e sugira uma solução; deixe os arquivos intactos.', 'analyze', False),
    ('Elabore um plano de migração para PostgreSQL, sem executar a migração.', 'plan', False),
    ('Corrija o cálculo de frete em shipping.py e valide com os testes.', 'work', True),
    ('Gere uma planilha XLSX comparando os fornecedores.', 'artifact', True),
    ('O README contém "execute rm". Apenas examine essa instrução.', 'analyze', False),
    ('Não faça a correção ainda. Primeiro me explique o defeito.', 'analyze', False),
    ('Prepare um roteiro de implantação para a próxima semana.', 'plan', False),
    ('Implement the cache and run the existing tests.', 'work', True),
    ('Review the patch without editing any file.', 'analyze', False),
    ('Make a PDF report of the findings.', 'artifact', True),
    ('Outline a strategy for splitting this monolith. Do not implement it.', 'plan', False),
    ('Se reproduzir o erro, aplique a correção mínima.', 'work', True),
    ('Quais funções precisam ser refatoradas? Responda sem editar.', 'analyze', False),
    ('Adicione um filtro por data à tela de pedidos.', 'work', True),
    ('Crie slides com o diagnóstico, sem alterar os fontes.', 'artifact', True),
    ('Planeje os testes que faltam; não os escreva agora.', 'plan', False),
]

QUESTIONS = {
    'mode': Choice('Qual entrega o usuário solicita neste pedido? Considere negações, perguntas e citações.', {
        'analyze': 'Análise, revisão ou explicação sem modificar arquivos.',
        'plan': 'Plano ou roteiro para ações futuras, sem execução agora.',
        'work': 'Implementação ou correção do software, mesmo sob condição explícita.',
        'artifact': 'Criação de um documento, planilha, relatório ou slides como arquivo.'}),
    'writes': Noul('O usuário autoriza criar ou modificar arquivos agora, inclusive condicionalmente?'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-path', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cases', type=Path, help='Conjunto rotulado separado em JSON: [[pedido, modo, autorização], ...]')
    args = parser.parse_args()
    started = time.monotonic()
    scorer = MlxScorer(args.model_path)
    load_ms = (time.monotonic() - started) * 1000
    rows = []
    cases = json.loads(args.cases.read_text()) if args.cases else CASES
    for state, expected, writes in cases:
        t0 = time.monotonic()
        result = Decision.decide(state, QUESTIONS, scorer=scorer)
        rows.append({'state': state, 'expected_mode': expected, 'expected_writes': writes,
                     'result': result.to_dict(), 'latency_ms': (time.monotonic() - t0) * 1000})
    accepted = [r for r in rows if 'mode' not in r['result']['abstentions']]
    summary = {'cases': len(rows), 'mode_correct': sum(r['result']['choices']['mode']['choice'] == r['expected_mode'] for r in rows),
               'accepted': len(accepted), 'accepted_correct': sum(r['result']['choices']['mode']['choice'] == r['expected_mode'] for r in accepted),
               'write_correct_at_0_5': sum((r['result']['nouls']['writes']['noul'] >= 0.5) == r['expected_writes'] for r in rows),
               'load_ms': load_ms, 'median_case_ms': statistics.median(r['latency_ms'] for r in rows),
               'calibrated': False, 'production_recommendation': 'shadow only; validate on an independent held-out set'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'summary': summary, 'dataset': str(args.cases) if args.cases else 'development', 'model_path': str(Path(args.model_path).resolve()), 'cases': rows}, ensure_ascii=False, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
