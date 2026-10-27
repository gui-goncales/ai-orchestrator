# Design system e wireframes

Antes das telas: superfícies carvão (#101113, #17191d), texto claro (#f1f2f4), secundário (#a5abb8), destaque lavanda (#b8a5ff); light: fundo #f4f5f7, superfície branca, texto #191b22. Espaçamento base 4px, raios 8/12px, borda discreta, foco lavanda de 2px, fontes system/Inter se instalada, mono para IDs/logs. Sem fontes externas obrigatórias. Estados sempre têm texto; movimento reduzido respeitado. Botões com altura mínima 38px, campos com labels, modais com Escape e foco inicial/restaurado, palette modal nativa.

Componentes: Button, Badge, Metric, Panel, TaskRow, EmptyState, Modal, Search, Toast, LogEntry. Tema system/dark/light com preferência persistida.

Wireframes funcionais:

```text
DESKTOP
┌ sidebar 220 ┬ projeto / breadcrumb ─── busca Cmd K ─ estado local ┐
│ Overview   │ título                         + nova tarefa       │
│ Workspace  │ métricas: agentes / execução / concluídas / tokens │
│ Tasks      │ agentes oficiais             atividade recente    │
│ Agents     │ tarefas persistidas e status                      │
│ Memory     │                                                   │
│ Analytics  │                                                   │
│ Activity   │                                                   │
│ Settings   │                                                   │
└────────────┴───────────────────────────────────────────────────┘
WORKSPACE: tarefas à esquerda | objetivo e saída central | checkpoint à direita
MOBILE: header com navegação select | métricas 2 colunas | cartões empilhados
MEMORY: busca | registros editáveis | checkpoints inspecionáveis
```

Kanban e lista compartilham as mesmas tarefas. Timeline inicial é o feed persistido de eventos; não há planejamento temporal editável. Gráficos usam contagens reais e barras sem estimativas fabricadas. Não alegar conformidade WCAG integral sem auditoria.
