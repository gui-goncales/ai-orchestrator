# AI Orchestrator

MVP local de supervisão de agentes, com PWA React, backend Python e memória SQLite independente do provedor. Não exige API paga. **Versão inicial, somente leitura; não é a plataforma completa descrita no prompt.**

## Iniciar no macOS

Requisitos: Node 20.19+ (ou 22.12+), npm, Python 3.9+ e pelo menos um provedor: Codex CLI com `codex login` usando ChatGPT, ou Antigravity com login Google. Elegibilidade e cotas dependem da conta. As CLIs Google e REA são dependências locais; Antigravity já está instalado nesta máquina.

```sh
cd /Users/guilherme/Documents/ai-orchestrator
npm ci
npm --prefix frontend ci
npm --prefix frontend run build
python3 -m backend.server
```

Abra [AI Orchestrator](http://127.0.0.1:8787). O backend deve permanecer ativo para executar tarefas. Fechar o navegador não encerra o backend. Para parar, Ctrl+C no terminal. Depois de reinício, use **Retomar do checkpoint** em tarefas interrompidas. Não execute dois backends com o mesmo banco. O lock atual usa `fcntl`: Windows requer adaptação; Linux/macOS são os alvos do backend atual.

No ambiente Codex com cache Python restrito, use `PYTHONPYCACHEPREFIX=/private/tmp/orchestrator-pycache python3 -m backend.server`.

## Usar

1. Confira Agents: escolha Codex com ChatGPT ou Gemini via Antigravity com Google. Nenhum segredo é solicitado no dashboard.
2. Crie uma tarefa de análise, planejamento ou revisão em modo leitura. Cada envio pode consumir a cota da assinatura.
3. Acompanhe saída, eventos e checkpoints no AI Workspace. Concluída significa resposta recebida com exit 0; revise o conteúdo para validar qualidade.
4. Exporte o pacote JSON de continuidade. Retomada reconstrói contexto externo; não transfere estado interno do modelo.
5. Registre diretórios em Settings → Registrar projeto. Somente faça isso para projetos autorizados. O sandbox read-only é nativo da CLI e não restringe toda leitura ao diretório do projeto.
6. Registre decisões em Memory. O backend inclui a memória do projeto, deduplica registros idênticos e rejeita excesso de contexto em vez de descartar silenciosamente requisitos.

## PWA e offline

Build servido pelo backend na mesma origem. Manifest, PNG 192/512, standalone e service worker estão incluídos. Use o menu de instalação de Chrome/Edge ou Adicionar ao Dock quando disponível. Permissões, instalação e splash dependem do navegador. Cache do shell e snapshot IndexedDB permitem consulta offline; comandos ficam desabilitados. Não há inferência offline. Ao reconectar o cliente recupera snapshot completo e eventos recentes. Limpar dados do navegador apaga apenas snapshot/preferências, não o SQLite.

## Comandos locais no modo Work

Selecione **Work · arquivos e comandos** para pedir ao agente que execute testes, builds
ou outros comandos do projeto. No modo automático, pedidos explícitos como
“Execute python3 -m unittest discover -s tests -v” são encaminhados para Work.
O modo **Analisar · somente leitura** não executa processos.

A ferramenta `run_command` aceita `command` (lista de argumentos ou string simples),
`cwd` relativo ao projeto e `timeout` em segundos (padrão 120, máximo 600).
Ela devolve `stdout`, `stderr`, `exit_code`, `status` e indicação de saída truncada
(limite de 64 KiB por fluxo). O agente recebe esses resultados para continuar.
O cancelamento da tarefa e o limite de tempo interrompem o grupo do processo.
Use chamadas separadas para cada comando; strings não recebem expansão de shell.

Comandos executam código local com as permissões do backend. A pasta de trabalho
é validada dentro do projeto, mas não constitui isolamento do processo: scripts
podem acessar outros caminhos. Use Work com projetos e comandos confiáveis.

## Validação

```sh
python3 -m unittest discover -s tests -v
npm --prefix frontend run build
```

O teste browser usa banco isolado em `/private/tmp/orchestrator-ui-test.sqlite3` e **adaptador falso**, nunca o provedor real:

```sh
PYTHONPATH=. python3 scripts/ui_fixture.py
# outro terminal: requer Playwright e Chrome
node scripts/browser-smoke.cjs
```

O script resolve primeiro o Playwright instalado no projeto; a cópia atual também aceita runtime empacotado do ambiente de desenvolvimento. Evidências em `evidence/`. Smoke real da CLI documentado separadamente; não confundir testes MOCK com integração ponta a ponta real.

## Segurança e dados

- Bind exclusivo em `127.0.0.1`, Host e Origin estritos, JSON em mutações e nenhuma permissão CORS. Não expor este servidor à rede.
- React escapa texto; sem HTML arbitrário. CSP e `nosniff` no shell. Sem credenciais em frontend, caches ou SQLite.
- CLI invocada sem shell, sandbox read-only, approval never. Chaves OpenAI/Codex removidas do ambiente do subprocesso. A autenticação deve indicar ChatGPT.
- Fila serial; checkpoint transacional; SQLite WAL; cancelamento/timeout encerram processo e grupo no POSIX.
- Dados em `data/orchestrator.sqlite3`. Backup consistente com `sqlite3.Connection.backup`, preferencialmente backend parado. O projeto não captura cookies nem lê arquivos de credenciais.
- Sem aprovação pelo dashboard: escrita e operações destrutivas não estão habilitadas. Read-only não impede que o provedor receba conteúdo de arquivos lidos: registre somente diretórios autorizados.

## Documentação

- [Pesquisa REA e fontes](docs/REA.md)
- [Arquitetura, persistência e recuperação](docs/ARCHITECTURE.md)
- [Design system e wireframes](docs/DESIGN.md)
- [Limitações e próximos gates](docs/LIMITATIONS.md)
- [Validação e benchmarks](docs/VALIDATION.md)

## Estrutura

`backend/core.py`: store, handoff v1, adapter e supervisor. `backend/server.py`: API/SSE e estáticos. `frontend/src`: UI React/TypeScript e tokens CSS. `frontend/public`: manifest, ícones e SW. `tests`: cenários determinísticos. `scripts`: testes isolados e benchmark sem IA.

## Novidades v0.2 — Google e dois modos REA

A [integração Google e REA](docs/GOOGLE-REA.md) substitui as limitações anteriores sobre ausência de adaptadores. `npm ci` na raiz instala Gemini CLI e REA fixados; Antigravity fica em `tools/bin/agy` para contas pessoais, pois o Google encerrou o serviço pessoal da CLI Gemini legada. Em Nova tarefa selecione agente e fluxo. A nova página **REA** oferece metodologia de três etapas retomáveis e análise estática de artefatos com o motor REA real. Autenticação Google, confiança do diretório e execução real devem ser validadas separadamente; instalação não é comprovação de disponibilidade.

## v0.3 — você descreve, o supervisor escolhe

O formulário não exige selecionar agente. O roteador usa disponibilidade e histórico, registra o motivo e não faz uma chamada LLM para decidir. Contexto preserva requisitos e remove duplicatas; referências explicitamente opcionais são selecionadas por relevância. Há critério opcional de saída exata e aceite humano de qualidade. [Política, métricas e limites](docs/AUTOMATIC-ROUTING.md). Redução percentual de tokens e qualidade equivalente entre modelos ainda não foram comprovadas por benchmark.

## Início persistente e recuperação

Para manter o backend independente da interface e reiniciá-lo se cair, execute `python3 scripts/start.py` em um terminal autorizado. O supervisor local não inicia automaticamente após reboot. [Diagnóstico, correções e limites da recuperação](docs/RECOVERY.md). Fluxos REA têm recuperação limitada para Codex quando Gemini encerra sem resposta pública; não há failover geral nem contorno de cotas.

## v0.4 — entregas após a pesquisa

O [fluxo de implementação](docs/DELIVERY.md) adiciona escrita por Codex em `artifacts/<task-id>`, validação estrutural, prévia em origem local separada e download ZIP. Em tarefas REA antigas, **Implementar este plano** continua a mesma tarefa sem repetir pesquisa. Objetivos novos de criação podem usar Entrega automática ou Criar artefato. Isso substitui a restrição anterior de somente leitura **apenas para a etapa de implementação no workspace isolado**; não autoriza escrita arbitrária nem publicação externa.

## v0.5 — o agente vê o artefato e propõe melhorias

Após criar o artefato, o supervisor captura telas reais desktop/mobile e envia os PNGs ao agente em uma revisão read-only. O dashboard mostra imagens e sugestões priorizadas. O botão **Analisar visualmente** também permite solicitar a análise, reaproveitada para a mesma versão sem outra chamada. [Fluxo, isolamento e limites](docs/VISUAL-REVIEW.md). Esta etapa propõe melhorias; não altera o código automaticamente nem substitui o aceite humano.

## Tess e outros modelos com login da conta

Em **Agents → Conectar pela conta**, use **Abrir login**, entre no provedor e abra uma conversa. Use **Verificar sessão** e selecione Tess em Nova tarefa, com Resposta ou Planejamento REA. O Tess tem mapeamento de interface incluído; outros sites precisam de seletores próprios. O backend usa o Chrome dedicado com a sessão pessoal, sem chave de API. Conexões por API da versão anterior não são carregadas nem aceitas. [Autenticação, evidência REA e limites](docs/SESSION-AUTH.md).
