> Histórico da implementação anterior. Substituída a pedido do usuário por [conexões com login da conta](SESSION-AUTH.md). O fluxo API não está ativo no orquestrador.

# Tess e modelos por API

Em Agents, cadastre uma conexão Tess ou OpenAI compatível. O cadastro guarda somente metadados e o **nome** da variável de ambiente da chave. Defina seu valor no ambiente que inicia o backend; reinicie o serviço após mudar esse ambiente. Nunca digite a chave no formulário. Para servidores locais sem autenticação, deixe a variável vazia.

Tess: use `https://api.tess.im`, o ID de um agente de chat sem ações externas, seu workspace e a variável `TESS_API_KEY`. Modelo é opcional: vazio usa o padrão do agente. A execução usa `tools: no-tools`, com consulta do resultado até conclusão. Cancelar interrompe a espera local; não garante cancelar o trabalho remoto. Chaves e cotas dependem da conta Tess.

OpenAI compatível: informe a URL base incluindo `/v1` quando exigido pelo serviço, o slug do modelo e a variável da chave. O conector acrescenta `/chat/completions`. Compatibilidade depende de o servidor implementar esse protocolo; APIs nativas diferentes exigem outro adaptador. Isso não significa suporte universal a qualquer site de chat. APIs recebem somente o contexto da tarefa e memória selecionada; não acessam arquivos locais nem implementam artefatos. Criação e revisão visual continuam com Codex.

Na tarefa, escolha a conexão para validar com uma chamada real (pode consumir créditos). Configuração salva aparece como validação pendente. Após uma execução bem sucedida, o roteamento automático pode usar essa conexão nas tarefas de texto e planejamento REA. Falhas de autenticação ou cota impedem seleção automática até nova execução explícita bem sucedida.

Investigação: o REA abriu a documentação pública num Chrome temporário, aguardou seu carregamento e capturou URL e acessibilidade. Não houve login nem execução paga. Evidence: `ev_3a9319b31ff82c6abdf467bd42f1710d9b9dd62df492ae6537591547d432c902`. A captura confirma a documentação publicada, não a disponibilidade de uma conta.

Fontes oficiais: [API](https://docs.tess.im/en/api-overview), [execução](https://docs.tess.im/en/execute-agent), [resultado](https://docs.tess.im/en/agent-response). Implementação verificada com servidor HTTP local e respostas simuladas; validação real requer credenciais do usuário.

Validação desta alteração: 71 testes Python passaram; build TypeScript/Vite passou; `node scripts/api-provider-smoke.cjs` cadastrou uma conexão e executou uma tarefa pela interface contra um servidor HTTP simulado, com verificação mobile e ausência de erros de JavaScript. Evidências em `evidence/api-providers-browser.json` e capturas desktop/mobile.
