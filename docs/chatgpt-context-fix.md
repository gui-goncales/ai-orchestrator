# Correção de contexto e captura do ChatGPT — 27/10/2026

O checkout inicial estava limpo e já continha envio incremental (`retains_conversation`) e lembretes menores. Não foi necessário reimplementar esse mecanismo. O backend anterior (PID 18612) tinha iniciado às 12:34:49, antes do commit local de main às 12:48:09. A inspeção não recuperou a versão em memória daquele processo.

A sobrecarga relatada é consistente com replay do histórico em uma conversa persistente. No código atual ainda havia duplicação do manual no primeiro envio e na recuperação de acesso. A extensão e a ponte também limitavam a espera a 180 segundos. A captura exigia observar geração ou um anúncio transitório; um relatório visível poderia terminar sem que esses sinais fossem capturados. Não foram recuperadas evidências suficientes para atribuir o erro histórico a um desses sinais especificamente.

## Alterações

- `backend/agent_engine.py`: preserva o envio incremental existente e o replay dos adaptadores sem memória; remove manuais duplicados, compacta lembretes sem repetir o plano, limita entradas a 180.000 bytes antes do envio e resultados individuais a 12.000 caracteres. Resultados completos e objetivos longos ficam em `.orchestrator-results/`, com indicação de leitura via `read_file`, `start_line` e `max_lines`. Saídas de comandos acima de 64 KiB também preservam cópia completa.
- `backend/web_providers.py`: vínculo por execução, metadados de tamanho/duração/envio/motivo e diagnóstico de falha local. Os eventos de diagnóstico não incluem o prompt nem credenciais.
- `backend/browser_bridge.py`: encaminha o vínculo, remove teto de três minutos e distingue timeout de despacho local de timeout de captura. Um job continua sendo entregue uma única vez.
- `browser-extension/chatgpt/worker.js`: verifica aba, URL, documento e quantidade de respostas entre rodadas; interrompe mudanças durante a geração; exige sinal explícito de conclusão ou controle final da resposta, além de ausência de geração e estabilização do texto. Não executa resultados parciais nem reenvia após timeout.
- `scripts/web-session.cjs`: verificações equivalentes no transporte Playwright, sem fallback para outra conversa vinculada, com controle final para ChatGPT e limite de resposta de 48 KiB.
- Testes: `tests/test_agent_engine.py`, `tests/test_browser_bridge.py`, `tests/test_web_providers.py`, `browser-extension/chatgpt/completion.test.cjs`, `scripts/web-session.test.cjs`.

## Validação

- `python3 -m unittest discover -s tests -v`: **142 aprovados**. O teste HTTP usa apenas loopback local.
- `node --test browser-extension/chatgpt/*.test.cjs scripts/web-session.test.cjs`: **12 aprovados**.
- `npm --prefix frontend run build`: **aprovado**.
- `git diff --check`: aprovado.

Fixtures demonstram múltiplas rodadas incrementais, replay sem memória, ausência de manual duplicado, truncamento recuperável, resposta lenta (inclusive conclusão depois de três minutos de relógio simulado), conclusão normal, timeout, captura sem sinal final, troca de conversa, vínculo por execução e uma única chamada após falha de captura confirmada. Nenhum teste enviou mensagens ao ChatGPT ou repetiu a auditoria completa.

## Ativação e limites

Após consultar novamente as tarefas e confirmar ausência de tarefas ativas, o backend recebeu SIGTERM e foi reiniciado pelo watchdog existente. Saúde confirmada em `/api/health`, com novo PID **23399** às **12:55:46 de São Paulo**. O serviço launchd não estava instalado; o watchdog foi preservado.

A extensão precisa ser recarregada em `chrome://extensions` para carregar o novo worker. Isso não foi feito automaticamente. A atualização do backend, por si só, não ativa o código da extensão.

Os testes dos transportes usam DOM/Playwright simulados; não provam compatibilidade dos seletores com a interface real atual. Mudanças nos controles finais podem causar uma interrupção conservadora. O transporte Tess preserva seu sinal de geração anterior; esta validação não estabelece um novo contrato de conclusão para Tess. Trocas de conversa são verificadas por amostragem e nas fronteiras de rodada; uma troca e retorno integralmente entre amostras pode não ser observada. Entradas acima do limite são rejeitadas explicitamente. Respostas do provedor acima do limite não são executadas parcialmente e exigem consulta à aba. Arquivos de resultados ficam no workspace e não têm limpeza automática; a leitura mantém o limite de arquivo de 20 MiB do WorkspaceTools.

O registro da auditoria `1fe148ddd130` foi comparado por hash antes/depois do reinício e permaneceu idêntico, com status **failed**. Suas evidências não foram recuperadas nem validadas; seu resultado não foi promovido a sucesso. A correção está validada localmente, mas a resolução na sessão real permanece pendente de recarga da extensão e validação posterior autorizada.

## Regressão identificada às 13h — transição provisória da conversa

A tarefa `86b47d19b824` falhou com `conversation_changed` após 4.695 ms, com envio ainda registrado como incerto. A consulta somente de leitura ao histórico do navegador recuperou a transição:

- 12:59:58.853: `/c/local-chatgpt%3A19fc7bb4-432d-4de6-b598-9aab2d8a7990`.
- 13:00:00.921: `/c/6ae0ca7e-fcb4-83e8-98ce-4bc8548fe433`.

Era a promoção do identificador provisório para o persistido, não uma troca demonstrada entre conversas. A proteção introduzida na correção anterior tratava qualquer mudança depois de `/c/` como troca real; esse foi um falso positivo.

Worker e Playwright passam a aceitar somente a promoção de uma URL provisória para um UUID persistido (ou o primeiro vínculo de uma página vazia), no mesmo documento e com o conteúdo da mensagem enviada preservado no último balão do usuário. Uma conversa persistida continua impedida de mudar de identificador. Transições sem a mensagem correspondente e uma segunda troca após a promoção são recusadas. Nenhuma mensagem é reenviada para recuperar a captura.

A inspeção somente de leitura da aba confirmou também o DOM atual: mensagem do usuário em `[data-user-message-bubble] .whitespace-pre-wrap` e término em ancestral `[data-talvt-turn-state="complete"]`. Os dois transportes agora reconhecem esses atributos sem depender apenas da estabilidade textual. A resposta já existente na aba era uma recusa de acesso às ferramentas, não evidência de execução da validação.

Validação desta revisão: **142 testes Python**, **23 testes JavaScript**, **build aprovado**, `git diff --check` aprovado. Foram acrescentadas fixtures da promoção, criação desde página vazia, ausência da mensagem correspondente, outra conversa provisória, troca após promoção e estados atuais `complete`/`streaming`. Não houve reenvio da tarefa nem novas mensagens ao ChatGPT.

A recarga automatizada da extensão foi bloqueada pela política de URLs do navegador para `chrome://extensions`. A recarga precisa ser feita pelo usuário; a revisão do worker ainda não foi ativada nem validada por novo envio real. Nenhuma tentativa de contornar esse bloqueio foi feita. As tarefas com falha não foram promovidas a sucesso.

## Falha das 13:13 — virtualização de turnos e canal de captura

A tentativa `9579487f93f6` iniciou às 13:07:22. Os eventos comprovam quatro respostas completas recebidas, envio incremental (8.958 bytes iniciais; depois 1.226, 1.226, 12.930 e 30.705 bytes) e 11 ações locais. Os cinco comandos registrados (`git status`, suíte Python, fixtures JavaScript selecionadas, build e `git diff --check`) retornaram status `ok` e exit_code 0. A quinta resposta não foi entregue ao backend: após 340.139 ms, a interface reportou genericamente “Extensão indisponível”.

A inspeção somente de leitura da conversa recuperou essa quinta resposta com estado DOM `complete` e novas chamadas propostas. Essas chamadas não foram executadas nesta investigação. O DOM continha quatro respostas: o primeiro turno anterior já não estava montado e o turno novo ocupava seu lugar. A captura aguardava `count > before`; portanto, não reconhecia a resposta nova quando a quantidade permanecia igual. A versão anterior também verificava o vínculo por contagem, o que poderia interromper rodadas por remoção legítima de turnos antigos.

Correções nesta revisão:

- Worker e transporte Playwright identificam a resposta pelo `data-chatgpt-selection-message-id` ou `data-message-id`, e mantêm o vínculo pelo último ID confirmado. A contagem é apenas fallback para interfaces sem IDs. Continuam exigindo conclusão explícita, texto estável e ausência de geração.
- `frontend/src/browserRelay.ts` e `frontend/src/main.tsx` usam um envio inicial seguido apenas de consultas curtas `poll` com ID da captura e da aba. A operação fica na página, evitando manter um único canal Chrome aberto durante toda a geração. Falhas do canal têm diagnóstico próprio e preservam confirmação de envio conhecida; nenhum `execute` é repetido.
- O worker memoriza IDs iniciados e resultados. Mesmo depois de expirar o texto de uma captura antiga, mantém um marcador que impede novo envio com aquele ID. Perda da página/contexto interrompe a captura em vez de iniciá-la novamente.
- `backend/decision.py` deixa de exigir mutação para “Se precisar corrigir o código…”. Esse trecho condicional do pedido de validação vinha gerando cobranças indevidas de edição. O teste de integração confirma conclusão após comando bem-sucedido sem alterar arquivos. `backend/agent_engine.py` também reconhece a recusa inicial observada de ausência do canal operacional para usar a recuperação compacta já existente.

O erro antigo descartava `runtime.lastError` e não permite comprovar retrospectivamente por que o canal fechou. O intervalo de aproximadamente cinco minutos, isoladamente, não prova uma causa específica no Chrome. A falha de detecção por contagem foi reproduzida com fixtures e corresponde ao DOM observado. O transporte novo elimina a dependência de um canal longo e diferencia falha de comunicação de ausência da extensão.

Validação final: **143 testes Python aprovados**; **34 testes JavaScript aprovados**, incluindo `tests/browser_relay.test.cjs`, fixtures da extensão e Playwright; **build aprovado**; `git diff --check` aprovado. Cobertura nova: resposta com contagem constante, vínculo com contagem reduzida e ID preservado, espera simulada acima de cinco minutos, perda do canal após envio confirmado, timeout inicial incerto, perda do contexto, comandos não duplicados e IDs expirados.

Sem tarefas ativas, backend reiniciado e saúde confirmada às **13:20:58**, PID **27081**. Os registros de todas as tarefas existentes foram comparados por hash antes/depois e permaneceram idênticos. A tentativa `9579487f93f6` permanece **failed**.

Ativação ainda depende de recarregar a extensão e a página do Orchestrator para carregar tanto o worker quanto o novo código da interface. O acesso automatizado a `chrome://extensions` permanece bloqueado pela política do navegador. Nenhuma nova mensagem foi enviada ao ChatGPT, nenhuma tarefa foi retomada e nenhuma auditoria foi repetida. Esta revisão foi validada localmente e por leitura da resposta existente, sem uma nova execução real ponta a ponta.

## Falha das 13:24 — bloqueio local ocupado por verificação de sessão

A tentativa curta `9e76cbda9ac3` falhou às 13:24:15.344 com “Sessão ocupada”, imediatamente depois de `model_input`. Esse texto vinha do retorno antecipado de `WebAdapter.execute`, antes de chamar `command` ou criar um job da ponte. **Nenhuma mensagem dessa tentativa foi enviada ao ChatGPT.**

O bloqueio era compartilhado entre `check`, `open_login` e `execute`. A atualização de conexões verificava `Supervisor.active` somente no início: uma verificação iniciada durante ociosidade podia continuar segurando o bloqueio quando a tarefa começasse. O registro antigo não identificava o detentor do bloqueio; a disputa com uma verificação foi reproduzida deterministamente com threads e fixtures locais, sem acesso ao provedor.

`backend/web_providers.py` agora distingue uma verificação de sessão de uma execução. Uma tarefa cancela apenas a verificação de leitura e aguarda sua liberação por até cinco segundos, dentro do orçamento da chamada. A verificação cancelada preserva o estado anterior da conexão. Cancelamento ou timeout durante a espera termina com `submitted=false`. Uma execução já em andamento permanece protegida, e outra execução não a interrompe nem envia comando concorrente. A espera e as recusas anteriores ao envio passam a emitir diagnóstico específico. O mutex não é liberado à força.

`backend/core.py` também reavalia a existência de tarefa ativa antes de cada provedor, evitando continuar a sequência de verificações após o início de uma tarefa.

Validação: **148 testes Python**, **34 testes JavaScript**, **build aprovado** e `git diff --check` aprovado. Os cinco novos casos cobrem preempção de verificação com exatamente um envio, cancelamento durante espera sem envio, verificação que ignora cancelamento com espera limitada, preservação de execução concorrente e interrupção da atualização entre provedores quando uma tarefa começa.

Esta revisão altera somente código Python do backend e seus testes. Não exige nova recarga da extensão. A tarefa curta não foi reenviada nem retomada automaticamente, e os resultados anteriores não foram promovidos a sucesso.

Backend reiniciado sem tarefas ativas às **13:27:50**, saúde confirmada com PID **28276**. Hashes de todos os registros presentes antes e depois do reinício permaneceram idênticos. A tarefa curta `9e76cbda9ac3`, lida no início do diagnóstico, já não constava no banco na verificação anterior ao reinício; esta intervenção não executou operações de remoção de tarefas. A validação real de duas rodadas continua pendente.

## Validação real mínima concluída às 13:33

O usuário executou o teste curto com ChatGPT explicitamente selecionado. Os eventos da tarefa **`4a50aa0530b2`** confirmam provedor **`web-chatgpt`**, status **`completed`**, resultado **`VALIDACAO_OK`** e ausência de erro ou alternância de provedor.

| Rodada | Entrada | Modo | Captura | Ação executada |
| --- | ---: | --- | --- | --- |
| 1 | 5.176 bytes | Contexto inicial, 2 mensagens | Envio confirmado; `response_complete`; 6.006 ms | `list_dir` para `.` |
| 2 | 3.577 bytes | Incremental, 1 mensagem | Envio confirmado; `response_complete`; 6.228 ms | `read_file` para `README.md`, linhas 1–5 |
| 3 | 2.274 bytes | Incremental, 1 mensagem | Envio confirmado; `response_complete`; 4.711 ms | `finish`, summary `VALIDACAO_OK` |

Cada ferramenta aparece uma única vez, na ordem solicitada. A leitura retornou exatamente cinco linhas, sem erro. O teste anterior com Tess (`d99bcebf68e5`) foi tratado separadamente e não foi usado como prova de funcionamento do ChatGPT.

O fluxo básico de três rodadas está agora validado em sessão real. Respostas longas/lentas, perda do canal, troca de conversa e virtualização continuam cobertas por fixtures, sem nova auditoria completa nem teste real destrutivo. A validação curta não reclassifica a auditoria histórica nem comprova todos os cenários de duração e tamanho.

## Falha das 13:35 — timeout de confirmação e versão do transporte

A tarefa `b52c784493aa` teve três respostas completas e cinco ações locais de leitura. Na quarta rodada, de 13.157 bytes, o frontend encerrou após 10.535 ms com **`extension_channel_timeout`**, confirmação de envio incerta. A resposta correspondente foi recuperada apenas por leitura da aba: estava em estado DOM `complete` e propunha quatro comandos. Esses comandos não foram executados nesta investigação e a tarefa não foi retomada.

O transporte anterior aceitava respostas finais de uma extensão sem negociação de capacidade. Isso permitia que uma implementação síncrona antiga concluísse chamadas rápidas, embora não suportasse o protocolo assíncrono solicitado. O teste curto bem-sucedido, portanto, comprovou o fluxo básico, mas não a versão/capacidade do worker ativo. O evento antigo não registrava a fase do canal nem a versão, impedindo atribuição retrospectiva conclusiva deste timeout a um worker específico.

Alterações desta revisão:

- Extensão **0.2.0**, com `bridge_protocol=2`, `capture_mode=async_poll` e ID da aba em respostas de verificação.
- `frontend/src/browserRelay.ts` negocia a capacidade por uma verificação somente de leitura antes de qualquer envio. Uma extensão sem confirmação do protocolo é recusada com `submitted=false`.
- Se apenas a confirmação inicial do envio se perder, consulta o ID já iniciado por `poll`. Nunca repete `execute`, inclusive quando a captura não existe mais. A confirmação tardia não provoca reenvio.
- `backend/web_providers.py` só habilita os controles da extensão com protocolo 2 e modo assíncrono confirmados. O estado da conexão expõe protocolo, versão e modo. Os eventos passam a registrar fase (`preflight`, `start` ou `poll`), ID do job e número de consultas, sem conteúdo do pedido nem credenciais.

Validação: **150 testes Python**, **38 testes JavaScript**, **build aprovado**, `git diff --check` aprovado. Fixtures adicionais comprovam bloqueio de extensão legada antes do envio, timeout na verificação com zero envios, recuperação após confirmação inicial incerta, ausência de reenvio quando a captura se perdeu e registro dos novos metadados.

Backend reiniciado ocioso às **13:42:45**, PID **30618**, saúde confirmada. Todos os registros de tarefas presentes permaneceram idênticos por comparação de hash; `b52c784493aa` continua **failed**.

A consulta posterior ao estado confirmou **`validation_required`**, sessão aberta, mas protocolo/versão/modo não informados pela extensão ativa. O backend agora bloqueia o envio nessa condição e informa a necessidade de recarregar a extensão **0.2.0**. É necessário recarregar também a página do Orchestrator, pois seu transporte mudou. A verificação de sessão, após essa recarga, pode confirmar o protocolo sem enviar mensagens ao modelo. Não houve nova execução real, reenvio ou promoção de auditoria a sucesso.

## Recuperação documental e revisão posterior — 27/10/2026

A consulta somente de leitura ao banco `data/orchestrator.sqlite3` e ao backup `data/backups/before-recovery.sqlite3` não encontrou a tarefa `1fe148ddd130`. O banco atual também não possui eventos ou checkpoints associados diretamente a esse ID. Há 21 eventos com menções indiretas ao identificador, mas eles não recuperam o relatório final nem comprovam a conclusão da auditoria. Nenhum status deve ser promovido com base nessas referências.

A tarefa `9579487f93f6` permanece `failed` no banco atual. Foram recuperados 56 eventos e 11 checkpoints: cinco entradas de modelo, quatro respostas capturadas e quatro submissões confirmadas. Os cinco comandos locais registrados (`git status --short`, suíte Python, testes JavaScript, build do frontend e `git diff --check`) terminaram com `exit_code=0`. A quinta rodada, com entrada de 30.705 bytes, terminou após 340.139 ms com `session_closed` e `submitted=null`. Isso comprova a execução dos comandos anteriores, mas não a captura da resposta final da quinta rodada. O campo `result` contém relatórios intermediários desatualizados e não deve substituir os eventos de execução. A comparação direta com o conteúdo atualmente visível nas abas do ChatGPT não foi realizada nesta revisão; não há evidência nova que permita classificar a resposta final como recuperada.

A inspeção do código atual incluiu `frontend/src/browserRelay.ts`, `backend/web_providers.py`, `backend/browser_bridge.py`, `backend/agent_engine.py` e `browser-extension/chatgpt/worker.js`. Os mecanismos existentes incluem negociação prévia do protocolo 2, captura assíncrona por consultas, identificação de respostas por ID, prevenção de reenvio após confirmação incerta e tratamento de timeout e perda de contexto. A cobertura por fixtures não equivale a comprovação em sessão real para respostas longas ou virtualização.

Nesta revisão, **150 testes Python**, **34 testes JavaScript**, o **build do frontend/PWA** e `git diff --check` terminaram com sucesso. Não foi identificada correção adicional de código com evidência suficiente para implementação. O banco ainda indicava `b52c784493aa` como `running`; por isso, o backend não foi reiniciado e nenhuma tarefa foi retomada. O teste real mínimo `4a50aa0530b2` não foi repetido.

**Próximo passo:** quando não houver tarefas ativas, recarregar a extensão ChatGPT 0.2.0 e a página do Orchestrator; verificar por leitura que `bridge_protocol=2` e `capture_mode=async_poll` estão ativos e comparar os relatórios já existentes nas abas com os eventos persistidos. Não reenviar tarefas com submissão confirmada ou incerta.

## Conferência do retorno da investigação posterior

O retorno anexado pelo usuário foi confrontado com os eventos persistidos da execução mais recente de `b52c784493aa`. O estado atual é **completed**, sem erro. A conexão confirmou **worker 0.2.0**, **bridge_protocol=2**, **capture_mode=async_poll**, sem erro de conexão.

Esta execução registrou **10 rodadas**, todas com `response_complete` e `submitted=true`: **um contexto inicial e nove entradas incrementais**. A maior duração de rodada foi **13.767 ms**, capturada por consultas assíncronas apesar de exceder os dez segundos do transporte anterior. Foram registradas oito leituras, 16 comandos, uma edição documental e duas chamadas de `finish`. O trecho do relatório que menciona a própria tarefa como `running` era uma observação feita durante sua execução, não seu estado final.

Houve uma rejeição indevida da primeira conclusão por ausência de mutação. A classificação lexical interpretava o componente **fix** de `docs/chatgpt-context-fix.md` como pedido de alteração. Isso explica a exigência que antecedeu a edição documental; a conclusão não deveria depender dessa edição.

Correção em `backend/decision.py`: caminhos, nomes de arquivos e URLs são excluídos apenas da detecção de verbos de mutação. A detecção de pedidos explícitos de comandos preserva o texto original; pedidos como “Corrija backend/fix.py. Execute tests/test_core.py.” continuam exigindo evidências. Testes em `tests/test_agent_engine.py` comprovam a classificação e a conclusão de revisão sem editar arquivos.

Validação desta correção: **152 testes Python**, **38 testes JavaScript**, **build aprovado**, `git diff --check` aprovado. Não houve nova mensagem enviada por esta investigação, nem repetição da auditoria ou do teste curto. A edição documental preexistente foi preservada.

O retorno ainda declara limitações reais: auditoria histórica ausente, relatório original não recuperado e ausência de comparação direta com abas naquela revisão. A execução maior valida o transporte em dez rodadas; não transforma a auditoria histórica em sucesso nem valida exaustivamente todos os cenários longos e de interrupção.
