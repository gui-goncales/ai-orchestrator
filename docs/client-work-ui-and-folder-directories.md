# Client Work e diretórios independentes por pasta

27/10/2026.

## Client Work

Página reorganizada em seleção de cliente, materiais de referência, criação e biblioteca de documentos. Upload por clique ou arraste; tipos de entrega com seleção visual; mensagens de estado em português. Editor apresenta o documento em vez de textareas permanentes: editar um trecho abre o campo e salvar cria uma nova versão. Histórico, aprovação da versão selecionada e exportação Word permanecem disponíveis. Layout de uma coluna no celular; navegação por teclado e rótulos acessíveis.

## Pastas do AI Workspace

A causa do problema era o compartilhamento de project_id entre pastas que existiam apenas como organização visual em localStorage. Alterar o projeto modificava o diretório visto por todas elas.

Agora workspace_folders persiste folder_id → project_id, com projeto próprio e diretório explícito para cada pasta. A configuração usa /api/workspace/folders e não altera o projeto compartilhado anterior. Nova conversa de uma pasta usa seu projeto vinculado. Pasta sem vínculo solicita conexão antes de enviar. O ícone “Vincular diretório” aparece ao lado do nome; ao criar uma pasta, a configuração já é aberta.

Conversas atribuídas à pasta são migradas para seu projeto durante a configuração. Migrações de conversas ativas ou com checkpoint incompleto são bloqueadas para não executar ações pendentes em outra raiz. Uma alteração de diretório só afeta o projeto daquela pasta. Mover uma conversa para outra pasta já configurada aplica a mesma validação. As pastas antigas não herdam automaticamente o diretório global: cada vínculo precisa ser configurado explicitamente.

Os nomes e o agrupamento visual de pastas continuam em localStorage, conforme a implementação anterior. Os vínculos de diretório ficam no SQLite. Excluir uma pasta da organização visual não apaga diretórios ou arquivos do dispositivo.

## Validação

- 243 testes Python aprovados, incluindo isolamento entre duas pastas, persistência do vínculo, migração de conversas concluídas, rejeição de diretórios inválidos e bloqueio de checkpoints pendentes.
- Teste HTTP real verifica dois diretórios independentes e preservação dos vínculos após reiniciar servidor isolado.
- Seis testes frontend e build aprovados.
- Chrome em ambiente isolado: criadas Cliente A e Cliente B com caminhos distintos; reaberta A após configurar B e confirmado caminho original. Nova conversa em A mostra a raiz de A.
- Chrome: edição de parágrafo cria versão 2 preservando outras seções. Layout desktop inspecionado; largura de 390px sem rolagem horizontal.
- Prévia: evidence/client-work-redesign.png e evidence/client-work-redesign-mobile.png. Dados fictícios; nenhum conteúdo real enviado a provedores.

Ativação: carregar backend atualizado e atualizar o aplicativo. Se o PWA apresentar “Atualizar agora”, concluir operações e salvar rascunhos antes de ativar, seguindo a proteção já existente.

## Correção de configuração duplicada

O formulário legado de ProjectContext foi removido: Arquivos e contexto é somente consulta, e toda alteração do vínculo ocorre no editor único da pasta. Enquanto esse editor está aberto, o painel de consulta fica oculto para não apresentar outra raiz como se estivesse sendo configurada.

Checkpoint interrompido pode ser associado ao projeto da pasta quando o diretório físico é exatamente o mesmo; o checkpoint permanece intacto. Mudança real da raiz com checkpoint pendente e migração de tarefas ativas continuam bloqueadas. Duas regressões adicionais cobrem esses casos.

Chrome em ambiente isolado confirmou um formulário de diretório, ausência do formulário legado e painel de contexto oculto durante configuração. Prévia: evidence/workspace-single-directory.png.

## Seletor nativo

No macOS, “Escolher pasta” chama o seletor nativo do dispositivo pelo backend local. A escolha retorna um caminho somente para conferência; não há campo para digitação manual, tanto no vínculo da pasta quanto no cadastro de projetos. O vínculo só é salvo ao confirmar a conexão. Cancelar o seletor preserva a seleção anterior e não cria um vínculo.

O script nativo é fixo, sem interpolação de dados e sem shell; usa ativação em primeiro plano, timeout e exclusão mútua para evitar diálogos simultâneos. O endpoint mantém as mesmas verificações locais de origem/Host/JSON. Esta implementação do seletor atende macOS; outros sistemas recebem indisponibilidade explícita, sem fingir ter selecionado um diretório.

Testes cobrem retorno, cancelamento, timeout, resultado inválido e plataforma. O formulário de teste recebeu a seleção /Users/guilherme/Documents/ai-orchestrator e a exibiu como texto, sem gravação em projeto real.
