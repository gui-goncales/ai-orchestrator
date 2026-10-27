# Validação realizada em 26/10/2026

## Integração real

Codex CLI `login status`: ChatGPT autenticado. Smoke direto via `exec --ephemeral --sandbox read-only --json` retornou `ORCHESTRATOR_OK`, exit 0, uso reportado 19033 input / 13184 cached input / 9 output. Evidência: `evidence/codex-smoke.json`. Consumo cached input é parte de input, não deve ser somado novamente. Essa chamada não alterou arquivos do projeto.

**Ainda não validado:** tarefa real atravessando HTTP → supervisor → adaptador → Codex. A revisão automática bloqueou um teste adicional que consumiria cota. Os testes browser abaixo não substituem essa validação.

## Testes determinísticos

15 testes `unittest`, todos passaram. Cobrem: criação idempotente, provedor/projeto inválidos, execução e uso, checkpoint, recuperação após reinício, cancelamento na fila e corrida de conclusão, proteção de tarefa já concluída, cota simulada sem agente alternativo, classificação por códigos explícitos, objetivo íntegro no pacote v1, rollback após falha de checkpoint, memória deduplicada, uso acumulado após retomada e serialização.

`npm --prefix frontend run build`: TypeScript e Vite passaram; SW recebe nomes reais dos assets para precache versionado. Bundle inicial JS ~264 kB (~80 kB gzip). Nenhum score de Lighthouse é inferido desse tamanho.

## Browser

Playwright com Google Chrome instalado, headless, banco e adapter **MOCK isolados**, sem provedor real. Verificados: render desktop; criação e resultado da tarefa falsa; dados persistidos; preferência de tema após reload; Cmd+K/Escape; ativação SW; reload offline com snapshot; mutações desabilitadas offline; reconexão; viewport 390px sem overflow horizontal; Origin externa rejeitada; criação idempotente pela API. Sem page errors. Evidência: `evidence/browser-smoke.json`. Capturas são do ambiente MOCK, identificadas como tal no cartão de autenticação.

Não executados: instalação manual do PWA pelo SO, Lighthouse, auditoria WCAG completa, notificações, Windows, segundo provedor e failover real.

## Benchmark local

50 tarefas MOCK com persistência SQLite; nenhum provedor chamado. Consulte `evidence/benchmark-local.json` para mediana/p95 medidos nesta máquina. Mede exclusivamente overhead de fila/checkpoint/persistência, não qualidade ou latência de IA. Tokens e economia não medidos.

## Protocolo proposto A/B/C (pendente)

Escolher fixtures de análise/revisão com critérios de aceitação idênticos. Repetir ao menos 5 vezes por cenário: A CLI direta; B supervisor com histórico integral selecionado; C supervisor com deduplicação/seleção. Mesma versão/modelo/workspace, variação de cache registrada. Registrar tempo monotônico, uso reportado, interações, testes determinísticos de resultado e avaliação cega de qualidade. Testar interrupção injetada e continuidade sem etapas repetidas. Publicar resultados brutos e limitações; não extrapolar economia de tokens de diferenças de caracteres ou de resultados MOCK.

## Atualização v0.2 — Google e REA

A validação Google real pelo backend passou, conforme `evidence/google-e2e.json`, usando Antigravity 1.4.7 e login Google oficial autorizado. A restrição anterior de ausência de teste real aplica-se ao Codex pelo backend, não ao novo adaptador Google. Gemini CLI 0.65.0 foi instalado mas recusou conta pessoal por migração de produto; não foi usado para contornar essa restrição.

24 testes do núcleo e integrações passaram. O browser também validou a nova página REA, três etapas persistidas com LLM falso e execução do **motor REA real** em artefato sintético pela UI. Nenhuma cota foi usada nesses testes REA. A única chamada Google real mínima está registrada separadamente. Build TypeScript/Vite passou. Zod 4.6.6 corrige o aviso de segurança detectado durante a instalação.
