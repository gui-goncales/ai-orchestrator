# Análise do orquestrador e prioridades

Análise do código disponível em 27/10/2026. As verificações estruturais não representam uma avaliação semântica completa da qualidade do agente.

## Diagnóstico

O sistema já possui persistência SQLite, histórico de conversas, execução local de ferramentas,
roteamento entre provedores e evidências registradas pelo runtime. O maior problema é que
interpretação, execução e avaliação ainda dependem de heurísticas e estados pouco separados.
O Decision ainda não é um planejador semântico completo: `plan_task` e
`completion_requirements` usam expressões regulares; uma frase diferente pode mudar a classificação.

## Prioridades

| Prioridade | Problema e evidência | Melhoria proposta | Critério de aceitação |
|---|---|---|---|
| P1 | `backend/decision.py`: requisitos de conclusão inferidos por palavras e exclusão de frases negativas | Contrato tipado de tarefa com objetivo, permissões, entregáveis, condições de aceitação e ambiguidades; validar contra a instrução original | Casos para paráfrases, negação, análise + implementação, continuação e instruções em arquivos |
| P1 | `backend/agent_engine.py`: escrita e comando com exit 0 são evidências estruturais, não prova de que a correção resolveu o pedido | Validar diff relevante, comando de teste apropriado, testes executados e resultado após a última alteração; etapa separada de avaliação | `rg` ou `echo` não satisfazem pedido de testes; arquivo irrelevante não satisfaz implementação |
| P1 | `WorkspaceTools.run_command` define cwd, mas processos têm as permissões do backend | Isolamento do processo e ambiente, limites de recursos, snapshot recuperável antes de autoalterações | Teste comprova limites de acesso; regressão gera restauração ou candidata separada |
| P1 | Autoalterações modificam o código e os testes do serviço em uso | Implementar em cópia candidata, preservar testes existentes, validar e apresentar diff antes de promover | Remoção acidental de teste é detectada; falha não altera a versão ativa |
| P2 | `backend/policy.py` e estado dos adaptadores misturam falha da tarefa com indisponibilidade do provedor | Saúde persistente por provedor/modelo, motivo, timestamp, cooldown e revalidação explícita | Erro de implementação não bloqueia serviço saudável; erro de autenticação não é apagado por consulta de catálogo |
| P2 | Histórico preservava resposta textual sem evidências; crescimento termina num limite rígido | Guardar mensagens, decisões e evidências como entidades; referências aos eventos, resumo verificável e orçamento de contexto | Continuação longa preserva requisitos e permite consultar evidências antigas sem duplicar tudo |
| P2 | `Decision.decide_failover` calcula probabilidade, mas a escolha do substituto não aplica todas as condições calculadas | Política explícita de falhas transferíveis, tentativas limitadas e preservação de checkpoint | Falha de código não provoca troca indiscriminada; provedor indisponível nunca é candidato |
| P2 | Sessão de navegador usa seletores e sinais sujeitos a mudança | Testes de contrato de UI, perfil específico por site e confirmação explícita de conclusão | Rascunho preservado, resposta antiga rejeitada e alteração do site falha com diagnóstico útil |

## GPT sem Codex

A conexão `web-chatgpt` é distinta de `codex`. O caminho preparado usa uma extensão local
no Chrome normal e uma aba explicitamente conectada pelo usuário, preservando o login do site.
O modelo GPT é escolhido na interface do ChatGPT. O backend continua executando as ferramentas
locais solicitadas pelo modelo. Não há promessa de acesso ao plano ChatGPT via API.

O login Google rejeitado na janela com depuração não deve ser contornado. A alternativa usa
o login normal do site; a extensão é conectada depois, com instalação e autorização pelo usuário.
Consulte `browser-extension/chatgpt/README.md` para permissões e instalação.

## Próximo trabalho recomendado

Começar pela avaliação de conclusão do Decision: separar “executou ferramentas”, “passou nos testes”
e “atendeu ao pedido”. Construir primeiro um conjunto de regressões com os casos reais deste projeto,
incluindo os falsos positivos de conclusão e as falhas de disponibilidade. Depois substituir progressivamente
as heurísticas pelo contrato de tarefa, preservando as permissões locais como regras determinísticas.
