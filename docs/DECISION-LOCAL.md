# Decision independente: inferência local, permissões e abstenção

## Estado atual

O Decision não depende da API do JEV. A inferência local está instalada e foi executada no Apple Silicon desta máquina (16 GB de memória). Nenhuma credencial habilita inferência remota.

A configuração local `.env` foi atualizada para `DECISION_MODE=shadow`, com o interpretador isolado em `tools/decision-runtime/bin/python` e o modelo em `data/decision-model-4b`. Essa configuração é lida na inicialização do backend; nenhum serviço existente foi reiniciado durante a mudança.

Em shadow, a classificação determinística continua autoritativa. A avaliação semântica é anexada como `semantic_review` ao contrato da tarefa automática; o modelo não muda a escolha nem as permissões. Falhas do modelo são registradas pelo tipo de erro, sem expor o pedido em mensagens de falha. Para desabilitar a inferência, use `DECISION_MODE=off`.

## Modelo e runtime

- Runtime: MLX LM 0.32.2, em ambiente Python 3.12 isolado do projeto. As versões efetivamente instaladas estão em `tools/decision-requirements.lock.txt`.
- Modelo selecionado para observação: `mlx-community/Qwen3-4B-Instruct-2507-4bit`, revisão `50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b` (aproximadamente 2,1 GiB no disco).
- Modelo pequeno testado e não selecionado: `Qwen/Qwen3-0.6B-MLX-4bit`, revisão `173234aa840d113125e9f2271100ddbaf16c9620` (aproximadamente 325 MiB).
- Pesos e runtime ficam fora do Git. Não são baixados implicitamente durante inferência. `trust_remote_code` permanece desabilitado.
- Fontes dos artefatos: https://github.com/ml-explore/mlx-lm e https://huggingface.co/mlx-community/Qwen3-4B-Instruct-2507-4bit.

`backend/decision_mlx.py` apresenta a pergunta e os critérios ao modelo usando alternativas A–Z. Lê diretamente os logits dos tokens correspondentes, sem gerar texto nem interpretar JSON produzido pelo modelo. As perguntas são processadas sequencialmente e de forma independente; não há sampler paralelo, compartilhamento de prefill entre perguntas ou reprodução demonstrada da arquitetura do JEV.

Os limites atuais são 26 alternativas por pergunta e 2.048 tokens por prompt; contexto excedido produz erro, sem truncamento silencioso. O bridge `backend/decision_runtime.py` envia a entrada por stdin a um subprocesso local com flags offline, limite de entrada de 64 KiB e timeout de 60 segundos. O subprocesso carrega o modelo em cada chamada; o custo de carregamento faz parte da latência do fluxo real.

## Intenção e autorização

Os workers recebem o mesmo contrato de capacidades aplicado pelo executor, inclusive na retomada. Veja [contratos dos agentes](AGENT-CONTRACTS.md).

`classify_mode` identifica uma entrega; isso não concede capacidades por si só. No modo automático, ausência de `authorization` concede apenas leitura. Trabalho inferido que exige escrita/execução fica com `permission_conflict`; o supervisor bloqueia antes de chamar o agente.

Um fluxo escolhido explicitamente (por exemplo, Work) preserva a autorização do fluxo. Grants podem ser fornecidos explicitamente como booleanos em `spec.authorization`:

```json
{"authorization":{"read_files":true,"write_files":true,"run_commands":true}}
```

Uma decisão semântica jamais expande esses grants. O contrato persistido também é aplicado na criação de WorkspaceTools para tarefas vinculadas ao Store: escrita não concede execução de comandos. Isso não transforma subprocessos em sandbox de sistema operacional; comandos autorizados continuam executando com as permissões do processo local.

## Abstenção e probabilidades

Sem inferência autoritativa, o identificador legado `local-heuristic` retorna distribuições uniformes (Choice/Score), Noul=0,5, confiança zero e `abstentions` para todas as perguntas. Esses valores existem para compatibilidade do formato: não são decisões válidas. Consumidores devem verificar `result.usable(question_id)`.

Com logits reais, `decision_scoring.py` aplica softmax estável, calcula o valor esperado de Score e a concentração por entropia normalizada em Choice/Score. Para Noul, mantém a distância de 0,5 como confiança legada. `calibrated` é sempre falso. Um resultado abaixo do limiar experimental de confiança 0,2 é marcado como abstenção. Esse limiar não foi calibrado e não elimina erros de alta confiança.

`DECISION_MODE=on` existe como modo experimental: uma classificação automática ambígua gera `decision_blocked`, que o supervisor bloqueia antes da execução. Esse modo não foi habilitado nesta máquina: os resultados atuais não justificam controle autônomo pelo modelo.

O failover usa uma política determinística separada quando não há inferência autoritativa: falha de serviço/cota reconhecida, candidatos elegíveis e desempate estável. Nesse caminho, a confiança é nula e os números neutros não justificam a troca. Com inferência autoritativa, exige perguntas utilizáveis e gates de continuidade. Não há promessa de equivalência semântica entre provedores.

## Avaliação real

Os pedidos usados são sintéticos, sem dados de clientes. O conjunto de desenvolvimento e o conjunto reservado têm 16 casos cada; não são representativos de toda a operação. Não houve treinamento nem calibração neste trabalho.

| Avaliação | Modelo 0,6B | Modelo 4B |
|---|---:|---:|
| Modos corretos no desenvolvimento | 5/16 | 14/16 |
| Modos corretos no conjunto reservado | não medido | 12/16 |
| Autorização de escrita, desenvolvimento (corte 0,5) | 9/16 | 9/16 |
| Autorização de escrita, reservado (corte 0,5) | não medido | 9/16 |
| Mediana por caso após carregamento, desenvolvimento | 195 ms | 1.151 ms |
| Mediana por caso após carregamento, reservado | não medido | 1.101 ms |

Cada caso tem duas perguntas. A mediana acima exclui o carregamento inicial, aproximadamente 2,6–3,3 segundos no modelo 4B. O smoke test do backend com subprocesso, uma pergunta e configuração shadow levou cerca de 3,75 segundos.

Os quatro erros de modo no conjunto reservado incluem uma instrução citada, uma negação em inglês e dois planos classificados como análise. Todos os 16 modos reservados ultrapassaram o limiar experimental de confiança; portanto, nesse conjunto a abstenção por entropia não filtrou os erros. A pergunta de autorização também teve desempenho insuficiente (Brier score aproximadamente 0,438). Por isso, autorização permanece determinística e o modelo fica apenas em observação.

Esses dados não são comparáveis diretamente aos 12 casos anteriores do JEV: são conjuntos e perguntas diferentes. Não há equivalência de qualidade nem de calibração demonstrada.

Arquivos locais de evidência:

- `artifacts/decision-local-evaluation.json`: desenvolvimento, modelo 0,6B.
- `artifacts/decision-local-evaluation-4b.json`: desenvolvimento, modelo 4B.
- `artifacts/decision-local-heldout-4b.json`: conjunto reservado, modelo 4B.
- `artifacts/decision-shadow-smoke.json`: configuração real do backend, subprocesso e preservação dos grants.

Para repetir a avaliação offline em Apple Silicon:

```sh
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 tools/decision-runtime/bin/python scripts/evaluate-decision-local.py --model-path data/decision-model-4b --cases tests/fixtures/decision-heldout.json --output artifacts/decision-local-heldout-repeat.json
```

A repetição deixa de ser uma primeira avaliação reservada; preserve os resultados originais e não ajuste o prompt contra esse conjunto sem separar novos dados de teste.

## Próximos critérios para promover o modelo

Expandir dados rotulados com exemplos reais anonimizados de engenharia de software, reservar um teste independente, medir custo de falsos positivos e curvas de confiabilidade, e avaliar alternativas de modelo/pontuação sem alterar permissões. Otimização por processo persistente e processamento em lote só deve vir com cobertura de timeout, concorrência e consumo de memória. A instalação atual é uma implementação independente de decisões tipadas, não uma reconstrução dos pesos ou do treinamento RLCD do JEV.
