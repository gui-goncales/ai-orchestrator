# Tess por token e seleção de modelos

O Tess usa a API oficial, com `TESS_API_KEY` somente no ambiente do backend (ou `.env` local, fora do Git). Reinicie o backend após alterar as variáveis. `TESS_WORKSPACE_ID` e `TESS_AGENT_ID` permitem substituir o workspace e agente já configurados. O agente deve ser do tipo chat. Nunca coloque o token em prompts, formulários ou logs.

Em Agents, use **Tess → Gerenciar → Verificar Tess**. No chat, selecione Tess e escolha **Modelo automático · Orchestrator** ou um modelo específico. As opções vêm de `GET /agents/{id}`, campo `questions[name=model].options`, e não de uma lista fixa. O catálogo da conta não garante saldo para todas as opções.

A seleção automática usa a complexidade do pedido e o fluxo: famílias rápidas para conversas simples e famílias de programação para trabalho e planejamento. É uma heurística pelos identificadores, sem preços, latência ou qualidade medidos. O modelo e o motivo ficam em `routing` e nos eventos da tarefa. Na ausência de catálogo, o modo automático usa o padrão do agente, explicitamente registrado.

Cada turno mantém o histórico local da conversa, inclusive após trocar de modelo. O protocolo envia `developer` no lugar de `system`, conserva a ordem das mensagens e mantém ferramentas nativas desabilitadas; as ferramentas locais continuam sendo executadas pelo Orchestrator no escopo do projeto. O orçamento atual de histórico é mantido; não há truncamento silencioso nem descoberta de janelas de contexto por modelo. Um limite remoto menor pode rejeitar a chamada.

No modo automático, uma rejeição HTTP 429 ou 503 ao iniciar uma execução permite uma única tentativa com outro modelo. A troca aparece no chat. Não há reenvio por falha de rede ambígua nem durante a consulta de uma execução já iniciada. A seleção manual não troca silenciosamente de modelo. Cancelar interrompe a espera local; a API pode continuar executando remotamente. A resposta aparece após a conclusão, sem streaming.

As conexões genéricas OpenAI compatíveis continuam desabilitadas no cadastro do supervisor. Esta alteração habilita o fluxo Tess por token.

Fontes oficiais: [autenticação](https://docs.tess.im/en/api-overview), [catálogo do agente](https://docs.tess.im/en/get-agent), [execução e papéis das mensagens](https://docs.tess.im/en/execute-agent).

Validação em 27/10/2026: 166 testes Python aprovados, mais uma regressão adicional de consulta remota aprovada, e build TypeScript/Vite aprovado. Teste real com token: descoberta de 213 opções; seleção automática `gemini-3.8-flash-low` retornou `TESS_TOKEN_OK`; troca manual para `gemini-4-argon-low` preservou a palavra `MARFIM` do primeiro turno. Foram enviadas apenas mensagens sintéticas, sem arquivos do projeto.
