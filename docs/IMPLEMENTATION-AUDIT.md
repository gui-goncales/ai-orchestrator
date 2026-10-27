# Revisão da implementação — 27/10/2026

A revisão do código e os testes identificaram divergências em relação aos relatos anexados.

## Corrigido

- Novo fluxo `work`, selecionável no chat e na criação de tarefas: o motor universal trabalha diretamente na pasta registrada do projeto. `deliver` e `improve` mantêm seus artefatos isolados.
- Painel de contexto recolhível com pasta vinculada, navegação de arquivos, leitura com linhas e memórias. Permite alterar o vínculo de um projeto existente, bloqueando a troca durante tarefas pendentes/em execução.
- Continuação da conversa mantém o projeto, objetivo e resposta dos turnos anteriores. O histórico tem orçamento explícito e não é truncado silenciosamente. Cada turno continua sendo uma tarefa persistida.
- Bloqueio de symlinks antes de resolver o caminho; bloqueio de caminhos absolutos, traversal e arquivos comuns de credenciais. Escritas usam arquivo temporário e substituição atômica.
- Limite de iterações não declara sucesso apenas porque existe index.html.
- Etapas REA de adaptadores com chat_turn recebem o motor de ferramentas em modo somente leitura.
- Resultados de ferramentas geram eventos persistidos e checkpoints do estado da tarefa.
- Pastas novas ficam vinculadas ao projeto ativo; a criação de conversa em pasta atualiza também o estado React.
- Inspetor mostra o nome do provedor configurado em vez de classificar APIs como Codex CLI.

## Validação

- `python3 -m unittest discover -s tests`: 100 testes aprovados, incluindo Work no projeto local, contexto entre turnos, isolamento entre projetos, symlinks e orçamento de execução.
- `npm --prefix frontend run build`: TypeScript e Vite aprovados.
- Chrome automatizado contra backend e banco temporários: painel de arquivos, leitura de conteúdo e seleção do modo Work verificados; nenhuma exceção JavaScript. Capturas desktop e mobile inspecionadas.
- Não houve chamadas a provedores pagos ou alteração de projetos reais durante a validação.

## Limites que permanecem

- O runtime universal usa protocolo textual estruturado; não implementa function calling nativo. A qualidade depende do modelo obedecer ao protocolo, portanto não há garantia de equivalência completa com o Codex Work para todos os modelos.
- As ferramentas locais cobrem arquivos; não há terminal universal nem execução arbitrária de testes/comandos pelo modelo.
- Os checkpoints de ferramentas registram estado e eventos, mas não restauram o transcript interno exato do AgentRunner. Retomada pode repetir inspeções/ações; não há garantia de execução exatamente uma vez.
- Organização de pastas e categorias usa localStorage, sem sincronização com IndexedDB ou backend. A afirmação anterior de sincronização IndexedDB era incorreta.
- O vínculo local usa um caminho absoluto informado pelo usuário; não há seletor nativo de pastas. O backend precisa rodar no mesmo dispositivo e ter acesso à pasta.
- A proteção implementada é uma fronteira de caminhos no processo local, não um sandbox do sistema operacional contra modificações concorrentes maliciosas no filesystem.
- Backend já aberto precisa ser reiniciado para carregar o novo fluxo e endpoints.

## Correção após uso real: análise direta com Tess

A captura do usuário mostrou uma tarefa `direct` em que a Tess negava acesso ao diretório. O projeto estava corretamente vinculado; o supervisor ainda usava uma chamada textual sem ferramentas nesse fluxo.

- Análises diretas de APIs e sessões web agora usam o motor universal em modo somente leitura, inclusive após failover.
- O runtime fornece a raiz autorizada e uma listagem real inicial, com instruções próprias de leitura e caminhos relativos.
- O estado do ApiAdapter é atualizado após chamadas multi-turn bem-sucedidas.
- Teste de regressão comprova leitura do README pelo modelo simulado e bloqueio de escrita no mesmo fluxo.
- Suíte atual: 101 testes aprovados. Leitura do README do projeto real via API local confirmada (94 linhas); backend reiniciado.
- A repetição com Tess real foi bloqueada pela revisão automática por exigir autorização explícita para enviar conteúdo do projeto ao provedor; não foi executada.

## Validação real autorizada com Tess

Após autorização explícita do usuário, a tarefa `57b1b34d31e0` foi executada com a Tess e concluída sem erro. Os eventos persistidos confirmam `read_file` para `README.md` e `package.json` e `list_dir` para `backend`, `frontend`, `docs`, `tests` e `scripts`, com resultados sem erros de acesso. Não houve mutação de arquivos nessa tarefa.

A primeira tentativa recebeu somente a listagem inicial e pediu arquivos manualmente. O protocolo textual foi também incluído na mensagem do usuário para compatibilidade com esse provedor; foi acrescentada uma tentativa de correção limitada para recusas indevidas de leitura. A segunda tentativa acionou as ferramentas reais. O modelo repetiu um lote de leituras e depois respondeu; isso confirma acesso ao diretório, sem constituir uma auditoria completa da qualidade da análise produzida.

Suíte atual: 102 testes aprovados. Backend em execução com os ajustes.
