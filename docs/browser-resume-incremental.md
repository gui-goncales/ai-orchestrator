# Retomada incremental no navegador

27/10/2026. A retomada inicializava delivered_messages em zero e enviava todo o transcript persistido para a conversa que já continha esses turnos, ultrapassando o limite de entrada de 180.000 bytes.

Para adaptadores com retains_conversation=true, um checkpoint com histórico envia somente a última mensagem de usuário pendente na primeira chamada da retomada. As chamadas seguintes continuam enviando apenas mensagens novas. A primeira execução continua enviando instruções iniciais; adaptadores sem conversa persistente mantêm seu contexto completo.

O histórico e o journal locais não são apagados nem compactados. Ações pendentes continuam sendo tratadas pelo mecanismo de retomada existente. Não há reenvio automático da tarefa, troca de conversa ou ampliação do limite de entrada. A aba vinculada deve permanecer na conversa original: começar uma conversa vazia não fornece o histórico remoto necessário.

Teste de regressão usa checkpoint com mais de 200 mil caracteres, verifica envio exato de uma única mensagem curta, sucesso sem estourar o limite e preservação integral do histórico local. A validação utiliza adaptador simulado, sem nova chamada real ao ChatGPT.

Correção adicional: Supervisor restaura o prompt inicial do checkpoint de execução em Work antes de chamar build_context. Antes disso, o resultado acumulado era reinserido como confirmed_result, estourando o limite de 80 mil caracteres antes de chegar ao envio incremental. Sem checkpoint válido, a construção e os limites originais permanecem. Regressão cobre resultado acumulado de 100 mil caracteres, restauração do pedido original e encaminhamento da mesma tarefa ao motor, sem reconstruir histórico.
