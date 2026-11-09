# Captura pendente após reinício do backend

27/10/2026 — extensão em disco 0.2.2.

A captura é mantida na página ChatGPT, independentemente do backend. Reiniciar o servidor não cancela nem recupera automaticamente essa captura. Um novo job não pode substituir o anterior sem risco de duplicar envio.

Na inspeção deste incidente, a última mensagem de assistente tinha innerText e textContent vazios, o ChatGPT mostrava resposta concluída e não havia botão de interrupção. A captura exigia texto não vazio para encerrar, mantendo o job pendente até timeout. O novo envio encontrava o bloqueio de captura em andamento.

Correção: resposta vazia com sinal explícito de conclusão encerra como interrupted/empty_response, com submitted=true; não é considerada sucesso. Nova execução enquanto outra captura existe retorna interrupted/capture_in_progress e submitted=false com orientação de recuperação, sem enviar mensagem adicional. Os IDs antigos continuam protegidos contra reenvio.

Validação: 28 testes da extensão aprovados, incluindo resposta vazia concluída e bloqueio de novo job. Não foi feita nova geração real nem retomada automática da tarefa.

Recuperação do incidente: confirmado banco sem tarefas running/queued e aba sem geração; recarregada apenas a aba ChatGPT, preservando a conversa e removendo o contexto de captura em memória. A extensão instalada ainda precisa ser recarregada manualmente em chrome://extensions para carregar a versão 0.2.2. A política da ferramenta bloqueia acesso à página interna; não foi tentado contorno.

Após recarregar a extensão, atualizar a página do Orchestrator e retomar a tarefa existente. Qualquer aviso de envio anterior deve ser reconciliado com a conversa; não criar tarefa duplicada para evitá-lo. A inspeção após reload também mostrou aviso do ChatGPT de capacidades reduzidas até 21:05, que não foi contornado.
