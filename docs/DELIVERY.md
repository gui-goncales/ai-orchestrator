# Após o REA: implementação e artefatos — v0.4

O fluxo de planejamento anterior produzia somente texto e não autorizava escrita. Agora a entrega separa marcos reais:

1. Research, Evaluate e Architect: leitura e planejamento.
2. Implement: Codex CLI oficial, sandbox `workspace-write`, somente na pasta `artifacts/<task-id>` criada para a tarefa. Nunca `danger-full-access` ou bypass. Aprovações indisponíveis falham em vez de ampliar permissões.
3. Validate: inventário com hash SHA-256, entrada HTML, JavaScript de aplicação e parsing com `node --check`. O backend não executa scripts npm gerados pelo agente.

O objetivo do usuário autoriza criar o produto nessa pasta isolada; publicação externa, operações destrutivas e escrita em outros projetos continuam fora do fluxo. Apenas o adaptador Codex com execução sandbox validada é elegível para a implementação atual; a escolha continua sendo do supervisor.

## Uso

Em Nova tarefa, Entrega automática identifica objetivos de criação comuns. É uma heurística transparente; escolha **Criar artefato** quando quiser explicitar a entrega de uma aplicação de navegador. **Somente planejamento REA** permanece disponível para pesquisa sem implementação. Tarefas antigas concluídas em REA têm botão **Implementar este plano**, que reaproveita as três etapas e continua a mesma tarefa.

Na execução, planning/ recebe os documentos confirmados e o objetivo. Dependência Three.js vem da instalação local fixada e é copiada para vendor/, com licença. O agente não precisa baixar pacotes ou depender de CDN. Ele deve criar um primeiro MVP real e registrar o que permanece pendente. Não existe promessa de transformar todo objetivo amplo numa versão premium completa em uma única chamada.

## Artefatos e isolamento de origem

A seção **Artefatos criados** apresenta caminho, lista de arquivos, **Abrir resultado** e **Baixar projeto ZIP**. A prévia é servida somente em `127.0.0.1:8789`, origem separada do dashboard em 8787. O servidor de prévia aceita apenas leitura, recusa caminhos fora do artefato e arquivos ocultos; o JavaScript gerado não recebe acesso CORS à API do orquestrador. O ZIP inclui o projeto e dependências vendorizadas, sem credenciais/configurações ocultas ou symlinks.

## O que significa validado

Criar arquivos e passar em parsing não comprova gameplay, compatibilidade, ausência de erros no navegador ou qualidade premium. O relatório estrutural explicita esse escopo. Testes de navegador e revisão de jogabilidade são documentados separadamente. Uma aplicação com arquivos mas falhas sintáticas permanece em revisão. Uma resposta textual sem index.html falha como implementação.

Para continuar após interrupção, etapas confirmadas permanecem em task_steps; implementação confirmada não é refeita apenas para revalidar arquivos. O estado da pasta isolada é preservado. Falhas de implementação antes do marco podem exigir nova chamada para continuar a pasta existente.
