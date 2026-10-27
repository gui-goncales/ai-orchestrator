# REA — 26/10/2026

## Gate de viabilidade

Codex CLI local 0.163.0-alpha.11.2: `codex login status` → `Logged in using ChatGPT`. Execução real, ephemeral, sandbox read-only: saída `ORCHESTRATOR_OK`, exit 0. Uso reportado: input 19033, cached input 13184, output 9. Isso comprova autenticação e execução mínima; não comprova edição, failover ou elegibilidade de qualquer outra conta. Primeiro ensaio no sandbox do ambiente falhou por acesso ao estado local; repetição autorizada fora dele funcionou. Nenhuma credencial foi lida ou copiada.

Gemini CLI ausente no PATH. Documentação oficial confirma login Google e reutilização de autenticação em modo headless. Segunda integração tecnicamente viável por caminho oficial, mas autenticação da conta e execução ainda dependem de validação. Gate suficiente para MVP de um provedor; failover de produção permanece bloqueado.

## Matriz conservadora

C = comprovado na documentação consultada; P = parcial; V = depende de validação; N = não suportado no escopo. Comprovação documental não equivale a teste local. Licenças não auditadas não são presumidas.

| Solução | Assinatura | API paga obrigatória | Automação | Handoff entre provedores | Memória | Failover | Tokens | macOS | Segurança / extensão | Licença | Maturidade observada |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Codex CLI | C + teste local | Não com ChatGPT elegível | C exec | P contexto externo | C sessões | V | C usage | C local | sandbox oficial / protocolos | V | CLI instalada alpha; fixar versão |
| Gemini CLI | C Google; conta V | Não em caminho Google elegível | C headless | P externo | C sessões | V | C cache | V local | políticas oficiais / MCP | V | documentação ativa; não instalado |
| OpenCode | C documentação de provedores; conta V | Depende do provedor | C CLI | V | C sessões | V | V | V local | servidor requer autenticação / extensível | V | docs v1/v2 divergentes; fixar versão |
| MCO (mco-org) | P via CLIs | Depende dos backends | C paralelo | P coordenação | V | V | V | V | herda segurança das CLIs | V | projeto ativo; sem teste local |
| CLI Agent Orchestrator (AWS) | P via CLIs | Depende dos backends | C tmux | C handoff/assign | C journal | V | V | V | sessões isoladas / providers | V | changelog 2.5.0 inspecionado |
| Agent Handoff (nick-vi) | P via CLIs | Depende dos backends | P | C contexto de sessão | P tópicos | V | V | V | herda HOME e regras; revisar | V | sem teste local |
| Continue | P conta Continue | Não para todo backend; cota V | C headless | V | P sessões | V | V | C docs | permissões de tools / MCP | V | CLI documentada |
| Roo Code | C docs Plus/Pro; conta V | Não para modelos locais | P extensão | V | P | V | V | V | depende do provider / extensão | V | docs atualizadas maio 2026 |
| Aider | V assinaturas | Não com modelo local | C scripting | P externo | C Git/contexto | V | P cache/mapa | V | ferramentas locais / backends | V | docs amplas, sem teste local |
| Antigravity | C docs Google Free/Pro/Ultra; conta V | Não no caminho pessoal documentado | C docs headless | V | P sessões | V | V | V | keyring oficial / SDK | V | docs atuais; não instalado |

Nomes MCO e Agent Handoff são ambíguos: esta matriz fixa os repositórios exatos abaixo. Outros projetos homônimos não foram tratados como equivalentes. Não foi feita auditoria de código, licenças ou todos os PRs/issues: itens V continuam pendentes. Changelog do CAO serve apenas como evidência de funcionalidades anunciadas.

## Estratégias

A: adaptar CAO/OpenCode reduz trabalho de runtime, mas acopla a UI e a segurança a protocolos e persistência externos. B: combinar CLIs oficiais + SQLite + supervisor próprio mantém autenticação com fornecedores e reduz superfície de integração. C: construir agentes e autenticação do zero aumenta manutenção e risco. Escolha B para MVP, sem frameworks multiagente adicionais nem inferência em decisões simples.

## Fontes primárias consultadas

- [Codex execução não interativa](https://learn.chatgpt.com/docs/non-interactive-mode): exec, autenticação existente, JSONL.
- [Codex autenticação](https://learn.chatgpt.com/docs/auth): mecanismos oficiais; assinatura não é API.
- [Gemini autenticação](https://geminicli.com/docs/get-started/authentication/): Google e headless.
- [Gemini headless](https://geminicli.com/docs/cli/headless/): saída estruturada.
- [OpenCode providers](https://dev.opencode.ai/docs/providers/): disponibilidade depende do provedor.
- [MCO](https://github.com/mco-org/mco): orquestração CLI e revisão paralela.
- [CAO](https://github.com/awslabs/cli-agent-orchestrator) e [changelog](https://github.com/awslabs/cli-agent-orchestrator/blob/main/CHANGELOG.md).
- [Agent Handoff](https://github.com/nick-vi/agent-handoff): continuidade por tópico.
- [Continue](https://docs.continue.dev/cli/quickstart): autenticação e headless.
- [Roo](https://roocodeinc.github.io/Roo-Code/providers/): provedores e modelos locais.
- [Aider](https://aider.chat/docs/llms): modelos locais e remotos.
- [Antigravity](https://antigravity.google/docs/install/): autenticação oficial.

## Riscos e limites

Uma resposta bem formada do modelo não comprova correção semântica. Cota restante não é inferível por tokens consumidos. Erros textuais genéricos não justificam failover. Nenhum estado interno de raciocínio é transferível. Cancelamento preserva eventos já confirmados; execuções interrompidas exigem retomada explícita. MVP não concede escrita a agentes nem promete isolamento de leituras fora do projeto pelo sandbox nativo. Não há telemetria externa da aplicação.
