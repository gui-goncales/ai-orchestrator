# Retomada segura de execuções

## Persistência

O Orchestrator mantém checkpoints versionados em `execution_states` (SQLite), incluindo o identificador estável da execução, histórico de mensagens, turnos, uso reportado, lote de ações pendentes, índice da próxima ação, evidências de comandos e hashes dos arquivos validados.

A tabela `tool_actions` registra cada invocação por `execution_id:turn_index:batch_index`, com argumentos, estado, resultado e hashes SHA-256 anteriores e posteriores para operações de arquivo. Os estados são `prepared`, `running`, `completed`, `failed` e `uncertain`. A intenção é persistida antes da execução. Ações concluídas ou falhas com resultado registrado não são despachadas novamente ao retomar.

## Interrupção e incerteza

Na recuperação, operações `running` tornam-se `uncertain`. Uma ação incerta **não é repetida automaticamente**, pois o efeito pode ter ocorrido antes da interrupção, inclusive em comandos externos. A retomada permanece bloqueada até que alguém examine o workspace e autorize explicitamente a repetição. O endpoint `POST /api/tasks/{task_id}/authorize-retry`, com JSON `{"action_id":"..."}`, registra a autorização e recoloca a ação em `prepared`; a interface apresenta o aviso e a confirmação correspondente. Autorizar não significa que a ação anterior foi desfeita.

Ações sem journal, provenientes de execuções legadas, não possuem a mesma garantia de granularidade. Não inferir sucesso apenas de uma chamada enviada ou de um relatório textual.

## Evidências e validação

Operações de arquivo registram o hash anterior antes do despacho e o hash posterior após o retorno. Uma validação bem-sucedida de `run_command` salva os hashes dos arquivos modificados. Se algum arquivo mudar após a validação ou durante uma interrupção, a evidência de validação é invalidada; é necessário executar novamente os testes pertinentes.

## Limites

Não existe garantia de execução exatamente uma vez para comandos arbitrários, serviços externos ou operações cujo processo caiu após o efeito e antes da confirmação. Nesses casos, a segurança é obtida bloqueando a repetição automática e exigindo reconciliação humana. A autorização manual pode repetir efeitos não idempotentes. Evite aprovar uma nova tentativa sem verificar o resultado anterior.
