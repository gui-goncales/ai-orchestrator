# Supervisor automático e contexto — v0.3

## Uso

Crie uma tarefa descrevendo o objetivo. O formulário não pede agente. A UI envia `provider=auto`; o supervisor escolhe no início da execução e registra decisão, candidatos e exclusões. Workspace mostra o agente efetivo e a justificativa. APIs de versões anteriores ainda aceitam seleção explícita, mas isso não é necessário no fluxo do usuário.

## Política verificável

Roteador determinístico, sem chamada LLM para escolher agente. Codex e Antigravity são candidatos de texto; REA é ferramenta de artefatos com fluxo próprio. Gemini legado não é substituto automático para contas pessoais.

Requer CLI instalada e autenticação indicada pelo probe ou execução anterior confirmada. Erro de autenticação/cota posterior bloqueia a candidatura. Histórico é consultado do mais recente para o mais antigo. O probe de Codex verifica login; o de Google não faz inferência para consultar login, então usa sucesso anterior até haver sinal contrário. Isto não garante cota restante ou validade eterna da sessão.

Entre elegíveis, usa conclusões estruturais da categoria da tarefa como evidência limitada de operação, não como prova de superioridade semântica. Não atribui capacidade por reputação de modelo. Empate é estável. Comparação por tokens só é habilitada quando todos os candidatos têm ao menos três amostras com uso reportado e qualidade aceita pelo usuário **para o mesmo objetivo e fluxo**. Mesmo assim, não é garantia estatística de qualidade futura.

Nenhum elegível: status blocked, sem consumir cota. Escolha fica fixa durante a tarefa e suas retomadas: não implementa failover geral. Exceção validada: etapa REA somente leitura que termina sem resposta pública no Gemini pode continuar em Codex, conforme RECOVERY.md. Restaurar acesso e retomar explicitamente uma tarefa bloqueada permite nova decisão se ainda não houve escolha. Sinais de cota não são contornados.

## Otimização com preservação

- Objetivo original e restrições integrais, sem resumo por LLM.
- Memórias preexistentes e tipo **Restrição ou requisito** são obrigatórias. Se excederem o orçamento, a execução falha explicitamente em vez de truncar.
- Referências só são opcionais quando marcadas assim pelo usuário. Recuperação por interseção de palavras, com orçamento de caracteres, registra IDs incluídos/omitidos. Não é recuperação semântica por embeddings.
- Deduplicação exata; uma referência nunca elimina uma restrição idêntica. Código/espaçamento internos não são reescritos.
- Contexto não repete metadados administrativos desnecessários. Resultado confirmado é mantido na retomada.
- Prompt não exige relatório operacional quando o usuário pede resposta curta/exata; isso corrige a divergência observada no primeiro teste simples.
- REA continua com três chamadas apenas quando o fluxo REA é escolhido. Tarefa direta não recebe revisão adicional por LLM nem fan-out.

Métricas em `context_metrics` e eventos: caracteres enviados pelo supervisor, baseline de memória sem seleção/deduplicação, estimativa caracteres/4 identificada como tal, duplicatas e referências omitidas, guardas de preservação. Não se apresenta redução de caracteres como economia real de tokens. Instruções internas acrescentadas pelas CLIs não são controladas integralmente pelo supervisor.

## Qualidade

Critério opcional **Resposta exata esperada** é verificado localmente. Falha resulta em needs_review, preservando o resultado e sem retry pago automático. Sem critério, conclusão significa resposta e exit 0; qualidade semântica permanece não avaliada. Botão **Aceitar qualidade** registra avaliação explícita do usuário. Não há promessa de manter qualidade em toda tarefa sem avaliação comparável.

## Evidências

Testes determinísticos cobrem indisponibilidade, roteamento sem LLM, persistência da decisão, contexto obrigatório, duplicatas, referência opcional, orçamento e formato exato. Teste navegador usa LLM falso; a análise de artefato REA é real em fixture sintética. Teste real mínimo com `provider=auto` é registrado separadamente em `evidence/auto-routing-real-test.json`. Sem benchmark A/B repetido, não declarar percentual de economia ou equivalência geral de qualidade.
