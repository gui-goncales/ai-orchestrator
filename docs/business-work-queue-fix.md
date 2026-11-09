# Client Work: fila, provedores e isolamento da interface

27/10/2026.

## Correções

- A rota de geração cria uma tarefa persistida no Store e retorna queued; não chama API dentro da requisição HTTP. O Supervisor executa essa tarefa pela fila serial existente, com cancelamento, eventos e checkpoints de tarefa.
- ChatGPT e demais provedores compatíveis usam o mesmo caminho. O fluxo gera conteúdo estruturado e não concede ferramentas de filesystem ao modelo. Provedores de análise estática REA e Gemini legado ficam excluídos. O frontend consulta a lista do backend em /api/business/providers, evitando oferecer opções rejeitadas pela própria geração. Um provedor já em execução pode receber uma nova tarefa na fila.
- A geração mantém task_id. Consultas reconciliam o estado da tarefa e finalizam a entrega de forma idempotente. Reinício recupera tarefas incompletas como interrupted; retomar exige ação explícita. O vínculo perdido entre criação de tarefa e attach_task é recuperado pela chave idempotente, sem criar nova tarefa.
- A interface acompanha a fila e oferece cancelar/retomar. Trocar cliente limpa fontes selecionadas, documento, título e mensagens; respostas atrasadas de outro contexto não substituem a tela atual. A troca fica desabilitada enquanto uma operação de formulário está em andamento.
- Cancelamento impede aceitar um novo documento após o retorno do modelo. Cancelar localmente não comprova cancelamento da geração remota do ChatGPT; os avisos do transporte e a necessidade de conferir envio anterior continuam válidos. Não se promete execução exatamente uma vez no serviço externo.

## Evidências

- tests/test_business_work_http.py: fila sem chamada síncrona, adaptador ChatGPT simulado, finalização sem documento duplicado, checkpoints, recuperação de reinício, retomada explícita, cancelamento e recuperação de vínculo.
- tests/test_business_http_server.py: sobe o servidor real com banco temporário e modelo simulado, exercita rotas de clientes/fontes/geração, espera o executor, edita um bloco, reinicia somente o servidor de teste e compara exportações das duas versões via HTTP.
- Frontend: seis testes existentes e build aprovados.
- Navegador Chrome contra servidor isolado 127.0.0.1:8891: seleção da fonte de Cliente QA A, troca para Cliente QA B com fonte desmarcada, geração na fila com IA simulada, abertura do documento e edição localizada confirmada como versão 2. Nenhum dado real de cliente ou chamada de IA paga foi utilizado.

Os testes de integração não comprovam disponibilidade da conta real do ChatGPT, qualidade semântica do modelo real ou layout do DOCX no Word/LibreOffice. Esses pontos não são declarados homologados por esta correção.

## Uso

Após carregar o backend atualizado e atualizar a página, abrir Client Work, selecionar cliente/fontes e um provedor conectado. Gerar cria tarefa na fila. A entrega aparece em Gerações quando concluída. Em interrupção, retomar a mesma geração; não criar outra para contornar um aviso de envio anterior.
