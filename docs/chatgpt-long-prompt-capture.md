# Interrupção na criação de conversa com prompt longo

Correção — 27/10/2026, extensão 0.2.1.

## Evidência

A tarefa `adaad1b12c8d` foi interrompida com `conversation_changed` no primeiro poll. O evento browser_round registra 14.431 bytes de entrada e worker_version 0.2.0. Inspeção somente leitura do DOM da conversa vinculada encontrou a bolha do usuário com exatamente 10.240 caracteres, tanto em innerText quanto em textContent. A conversa já tinha resposta concluída no site; isso não significa que ferramentas locais tenham sido executadas.

Durante a promoção de uma conversa nova de URL provisória para definitiva, a captura exigia igualdade entre a bolha e o prompt inteiro. A representação truncada impedia essa igualdade.

## Correção

worker.js e scripts/web-session.cjs reconhecem o prefixo somente no limite observado de 10.240 caracteres e somente se o prompt original for maior. Igualdade do texto completo continua aceita. Mantidos os limites de origem, transição de conversa nova/provisória e eco da mensagem. O caminho Playwright continua verificando também o token do documento. Prefixos arbitrários ou diferentes continuam interrompendo a captura. Não há reenvio automático ou execução de resposta parcial.

Limite: uma representação truncada não comprova identidade do sufixo omitido. A verificação usa a transição permitida no documento em captura e igualdade de todo o prefixo exposto; não pretende autorizar migrações entre conversas estabelecidas. Se o site mudar seu limite ou forma de apresentação, será necessária nova validação.

## Validação

- `node --test browser-extension/chatgpt/completion.test.cjs browser-extension/chatgpt/worker.test.cjs scripts/web-session.test.cjs`: 39 testes aprovados.
- `python3 -m unittest tests.test_browser_bridge tests.test_web_providers -q`: 26 testes aprovados.
- Regressões cobrem promoção com prompt longo, prefixo divergente, prefixo curto, troca de conversa, ausência de eco, resposta parcial e duplicação de captura.
- Não foi feita nova chamada real ao ChatGPT nem retomada da tarefa. O comportamento corrigido foi validado com fixtures; a evidência do limite veio da conversa real.

## Ativação

No Chrome, abrir manualmente `chrome://extensions`, localizar **AI Orchestrator · ChatGPT** e recarregar a extensão. A versão em disco é 0.2.1. A ferramenta de navegador bloqueou acesso à página interna, portanto a extensão ativa não foi recarregada por esta correção.

Manter a aba ChatGPT conectada na conversa desejada e atualizar a página do Orchestrator. Usar a retomada existente, observando qualquer verificação de envio prévio: o provedor pode ter recebido e respondido ao pedido apesar da captura interrompida. Não criar tarefas duplicadas para contornar essa confirmação.
