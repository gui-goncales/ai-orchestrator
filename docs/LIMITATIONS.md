# Limitações explícitas

Atualização v0.2: consulte [Google e REA](GOOGLE-REA.md). Os adaptadores Google e o motor REA agora estão integrados. A execução mínima Google via Antigravity foi validada; a metodologia REA de três etapas foi testada com agente falso. As limitações abaixo foram atualizadas para esse escopo.

## Entregue no MVP

Pesquisa inicial com fontes, arquitetura e wireframes; Codex autenticado confirmado por smoke real mínimo; adaptador Codex somente leitura; tarefas e projetos locais; fila serial; logs de mensagens públicas; memória editável; checkpoints transacionais; exportação de handoff v1; cancelamento; retomada manual; SSE; dashboard baseado em SQLite; métricas reportadas; lista/Kanban/feed; tema e palette; manifest/SW/snapshot offline.

## Não considerar entregue

- CLI Gemini legada não serve a conta pessoal; acesso Google funciona pelo adaptador Antigravity validado. Failover entre provedores continua pendente.
- Failover automático entre provedores, transição semântica validada e gerenciamento de cotas restantes.
- Edição autônoma, worktrees, snapshots de arquivos, rollback de alterações, publicação ou aprovação de ferramentas no dashboard.
- Planejador de dependências, progresso percentual comprovado, prioridades ou timeline editável.
- Compactação por LLM, embeddings, ranking semântico, cache de respostas e economia comprovada. Otimização atual é deduplicação exata e seleção de memória por projeto.
- Markdown com syntax highlighting, visualizador de arquivos, React Flow e painéis com redimensionamento completo. Saída é texto seguro preformatado; alguns painéis desktop têm resize nativo.
- Retenção configurável, comparação visual entre checkpoints e exclusão de tarefas. Memórias podem ser editadas/excluídas com confirmação.
- Notificações de SO, atualização coordenada do SW com aviso ao usuário, Lighthouse e auditoria WCAG 2.2 AA.
- Instalação PWA manual confirmada em cada sistema/navegador, splash em todos os sistemas.
- Suporte backend Windows (lock POSIX), autenticação multiusuário, TLS, acesso remoto ou distribuição instalável do backend.
- Benchmark real A/B/C com provedores e avaliação de qualidade. O benchmark local mede apenas o supervisor com adapter falso.

## Gates seguintes

1. Validar task real pela API do backend: o smoke direto da CLI já passou, mas não substitui esse teste. Execução adicional com cota foi bloqueada pela revisão automática do ambiente; requer autorização explícita para o teste adicional.
2. Instalação e login Google concluídos via Antigravity; smoke real pela API passou. Validar tarefas representativas e limites de uso antes de failover.
3. Adaptadores Gemini/Antigravity implementados, parsing com fixtures testado. Ainda testar cota real e políticas específicas sem provocar consumo desnecessário.
4. Validar handoff com critérios idênticos e sem repetir etapas confirmadas, antes de automatizar failover.
5. Escrita somente após workspaces isolados, diffs, testes e política de aprovação para ações sensíveis.
6. Benchmark A/B/C repetível com cota autorizada e sem extrapolar economia a partir de testes falsos.

As assinaturas são contratos de produtos; não são chaves de API. A documentação pode mudar. Fixe e revalide versões das CLIs antes de atualizar.
