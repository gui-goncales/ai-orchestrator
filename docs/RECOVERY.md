# Correção da tarefa 916cb60f6365 e backend offline

## Diagnóstico observado

A tarefa indicava `Antigravity: SUCCESS` como erro. Na realidade, o processo havia retornado exit 0 e status SUCCESS, mas o campo de resposta pública estava vazio. Não havia etapas REA confirmadas. Depois, a porta 8787 estava sem listener; a UI exibia seu snapshot IndexedDB offline. Dados e objetivos permaneceram no SQLite.

O teste curto do protocolo público confirmou eventos documentados `agent_response/text_delta`. Capturar esses eventos não recuperou texto para a tarefa longa: o provedor também não emitiu fragmentos públicos nessa execução. Não foi usado raciocínio interno ou texto de ferramentas como substituto de resposta.

## Correções

- Adapter captura o protocolo stream-json e usa somente resposta final ou deltas públicos de agent_response. O resultado é publicado após captura; a interface não simula streaming.
- Relatórios REA podem usar schema estruturado com report não vazio. Status SUCCESS vazio continua sendo falha, com mensagem explícita e diagnóstico, nunca sucesso fictício.
- Etapas REA instruem o agente a produzir relatório público da etapa, em vez de executar toda a implementação contida no objetivo.
- Recuperação limitada: após ausência de resposta pública no Gemini em etapa REA read-only, o supervisor pode selecionar Codex autenticado. Na retomada de uma falha já registrada, troca antes de fazer outra chamada ao Gemini. Mantém objetivo, etapas confirmadas e uso reportado. Não troca por falha de autenticação ou cota; não permite escrita.
- Exceção inesperada de uma iteração não encerra silenciosamente o worker.
- `/api/health` responde sem depender de chamadas de autenticação a CLIs.

## Backend independente da conversa

Um LaunchAgent foi preparado, mas o macOS negou ao processo em background acesso ao projeto dentro de Documents. O agente foi removido; nenhuma permissão de privacidade do sistema foi alterada.

Foi iniciado um supervisor local desacoplado usando o ambiente autorizado:

```sh
python3 scripts/start.py
```

Ele detecta backend já ativo, mantém PID em data/watchdog.pid e reinicia o backend após saída. Logs: data/service.log, data/service-error.log e data/supervisor.log. Um reinício real do filho foi testado sem tarefa ativa; evidência em evidence/watchdog-restart.json. Não é um daemon privilegiado, não expõe a rede e não inicia inferência por si só. Reinício do computador ainda exige executar start.py; o instalador launchd opcional não está ativado por causa da restrição de Documents. Não prometer inicialização automática no login nesta configuração.

O desligamento do backend marca trabalho incompleto como interrupted na próxima inicialização e requer retomada explícita; não repete chamadas pagas silenciosamente.

## Evidências e escopo

Backup consistente do banco antes do reparo: data/backups/before-recovery.sqlite3. Evidências do protocolo público em evidence/antigravity-public-protocol.json. Resultado da recuperação em evidence/recovery-916cb60f6365.json.

A tarefa em fluxo REA entrega pesquisa, avaliação e arquitetura. O código do jogo descrito no objetivo não é gerado por esse fluxo: o ambiente continua somente leitura. Não confundir conclusão do plano com implementação ou jogo validado.


## Recuperação concluída

A tarefa original 916cb60f6365 terminou em completed, sem erro, pelo Codex. Research, Evaluate e Architect estão persistidas, com 34.020 caracteres de resultado agregado. Nenhuma tarefa duplicada foi criada; a outra tentativa antiga 50aaf9158760 não foi reexecutada. O resultado legível está em evidence/rea-dead-zone-recovered.md. Foram aprovados 42 testes automatizados. Browser confirmou conexão e exibição da tarefa original sem page errors.
