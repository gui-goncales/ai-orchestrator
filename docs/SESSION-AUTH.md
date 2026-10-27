# Conexões pela conta

O fluxo ativo do orquestrador usa autenticação das CLIs (Codex, Google) ou a sessão de uma janela Chrome dedicada (Tess e outros sites configurados). Não solicita chave de API. Configurações API antigas ficam preservadas no banco como histórico, mas não são carregadas, selecionadas ou aceitas para novas tarefas.

## Usar Tess

1. Em Agents, selecione Tess em Conectar pela conta. O mapeamento do chat já vem incluído.
2. Clique em Abrir login. Entre diretamente no site Tess com sua conta. O orquestrador não preenche e-mail, senha ou MFA.
3. Abra uma conversa e clique em Verificar sessão. A disponibilidade de controles não comprova uma resposta do modelo: o estado fica Validação pendente até uma execução concluída.
4. Crie uma tarefa com agente Tess e fluxo Resposta ou Planejamento REA. O conector preenche o campo, clica em Enviar, aguarda o indicador de geração aparecer e desaparecer e captura somente o conteúdo público da resposta do assistente. Sem dados de tokens disponíveis, o uso permanece desconhecido.

Mantenha o Chrome dedicado aberto. O perfil fica em `data/browser-profiles/tess`, com diretório privado e fora do versionamento. O navegador administra os cookies de sessão nesse perfil; o conector não os exporta nem reproduz endpoints internos. CDP escuta em loopback com porta dinâmica; outros processos do mesmo usuário podem controlar esse navegador. Não use o perfil para outros sites ou tarefas pessoais.

## Outros modelos

Adicione uma conexão `web-nome`, com URL HTTPS de login e de chat no mesmo site. Faça login e mapeie seletores CSS para campo da mensagem, botão Enviar, conteúdo das respostas do assistente e indicador de geração. O mapeamento Tess foi observado na sessão real; cada outro site exige validação própria. Não há autenticação OAuth universal para todos os sites. Um site pode impedir automação ou mudar sua interface; o conector deve falhar e pedir nova verificação, sem recorrer à API.

## Execução e limites

- Sessões web suportam texto e planejamento REA; implementação de arquivos e revisão de imagens continuam usando as CLIs habilitadas.
- A sessão usa a conversa que está aberta; o histórico dessa conversa pode influenciar a resposta. Abra uma conversa vazia para um objetivo independente. Não escreva nela durante a execução.
- Rascunhos existentes são preservados; o conector recusa sobrescrevê-los. Múltiplas conversas ambíguas bloqueiam a execução.
- Cancelamento/timeout interrompe a espera local e pode deixar geração remota em andamento. Confira o site antes de retomar; não existe garantia de envio único após falha de conexão.
- O conector não concede acesso a arquivos locais. As ferramentas e conectores disponíveis na conta do provedor dependem das configurações dessa conversa; selecione um chat sem ações externas para tarefas de análise. Um prompt de somente leitura não é um sandbox remoto.
- Sessão expirada, erro de interface ou falta de comprovação de término não são reportados como conclusão. A elegibilidade e a cota continuam dependentes da conta.

## Evidência REA

O REA abriu o login público em um Chrome temporário (`ev_39555c3ce6a8a62cbd99c7e683d928edb551f93ffd019f95509ed4b0e5632407`). O usuário realizou o login manual na janela dedicada e abriu a conversa. O REA descobriu o alvo e inspecionou passivamente a página autenticada (`ev_393f3b584a18e2938a5fc3becbda33560ca1a8cec2d8a4f78acdfe1fd0e33408`). Estrutura do formulário e templates publicados fundamentaram os seletores; código de estado visual confirmou classes de geração. A execução é feita pelo adaptador do orquestrador via interface, não pelo REA passivo.

Fontes públicas: [login Tess](https://tess.im/pt-BR/login), [MCP Tess](https://docs.tess.im/en/api-mcp). O MCP documentado usa token de API e não resolve o requisito de login da conta; por isso o fluxo usa a sessão de navegador.

Testes: suíte Python; build TypeScript/Vite; `node scripts/web-session-smoke.cjs` testa envio, término observado, proteção de rascunho e rejeição de login em fixture local. `scripts/tess-auth-validate.py` cria uma tarefa real pelo servidor ativo para validar a conta, com resultado em `evidence/tess-auth-real.json`. Esse script pode consumir créditos da conta e não deve ser executado repetidamente sem necessidade.

Validação real concluída: tarefa `93606b5bc48f`, agente `web-tess`, resposta `TESS_AUTH_OK`, estado `completed`, critério de saída exata aprovado. A sessão autenticada foi usada diretamente pelo backend em execução, sem API key. O serviço real foi reiniciado quando estava ocioso e a nova conexão está ativa.

## Página Agents

A página separa Meus agentes, descoberta de provedores e ferramentas locais. Busca e filtros mostram conexões prontas ou que precisam de atenção. Cada cartão oferece uso direto (com agente pré-selecionado na tarefa) e gerenciamento.

Conectar agente abre três etapas: escolher serviço ou Outro provedor, informar nome e endereço HTTPS e fazer login. IDs de novas conexões são gerados automaticamente, inclusive para múltiplas conexões com o mesmo nome. Campos técnicos ficam recolhidos nas configurações avançadas. Não é necessário fornecer seletores para cadastrar ou abrir o login de um site novo.

Ao verificar a sessão, o conector tenta reconhecer campos de mensagem e marcadores comuns de resposta e geração. Somente controles observados são sugeridos, sem enviar mensagens ou ler cookies. As sugestões são salvas no cadastro e verificadas novamente. Se a interface não expõe marcadores reconhecíveis, o ajuste manual continua necessário. Cadastro e login não equivalem a suporte de execução comprovado; cada site precisa de validação. Conexões idênticas salvas novamente preservam o estado já validado.

Validação de UX: 77 testes Python, build TypeScript/Vite, fixture de navegador com descoberta de controles e cadastro real em backend isolado. `scripts/agents-ux-smoke.cjs` verifica filtros, busca, erro HTTPS, cadastro personalizado, persistência do ID, diálogo com Escape, layout mobile e seleção de agente na tarefa. Capturas e resultado em `evidence/agents-ux*`.

## Detecção após login e reinício

A disponibilidade da conta é verificada ao iniciar o servidor e a cada 15 segundos, em segundo plano, sem geração de respostas. O Tess precisa de sessão autenticada e controles mapeados para exibir Usar agente. A janela dedicada fechada aparece como Sessão fechada, com ação de reabertura; isso não significa que as credenciais salvas foram apagadas. A verificação passiva não traz o navegador para frente.

O Antigravity consulta o comando oficial `agy models`, com variáveis de API removidas, sem ler arquivos de credenciais nem exportar stderr. Uma resposta válida da lista habilita o uso da conta. O campo `execution_validated` distingue uma execução bem-sucedida de uma verificação de disponibilidade. Falhas de consulta são apresentadas como validação pendente, não como login ausente sem evidência.

A detecção é refeita após reinícios, sem persistir uma suposição de sessão válida. Não roda durante uma tarefa ativa. O modo de backend com adaptador de teste não inicia consultas reais aos provedores. Regressões cobrem rechecagem após reinício, sessão expirada/fechada, catálogo inválido e separação entre conexão disponível e inferência confirmada.
