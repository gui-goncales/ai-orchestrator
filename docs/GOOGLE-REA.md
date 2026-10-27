# Integração Google e REA — versão 0.2

## Google: mudança verificada em execução

Instalado `@google/gemini-cli` 0.65.0, fixado em package-lock.json. O login Google da CLI informou encerramento do serviço Gemini Code Assist para indivíduos e encaminhou ao Antigravity. O [anúncio oficial](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/) confirma o encerramento para Free/Pro/Ultra em 18/06/2026; licenças empresariais elegíveis continuam na CLI legada. A pesquisa anterior apenas pela página de autenticação era insuficiente; esta descoberta substitui a conclusão anterior para contas pessoais.

Instalado Antigravity CLI 1.4.7 em `tools/bin/agy`, usando manifest oficial referenciado pelo instalador Google e verificação SHA-512. Não foram alterados perfis do shell. Login e confiança de workspace usam exclusivamente o fluxo oficial. Credenciais são geridas pelo fornecedor, não pelo aplicativo.

```sh
npm ci
python3 scripts/install-antigravity.py  # somente se tools/bin/agy ainda não existir
./tools/bin/agy                        # login Google e confiança explícita no diretório
```

O formulário de tarefas oferece **Gemini · Antigravity (conta pessoal)** e **Gemini CLI legado · licença empresarial elegível**. Não configurar chaves de API pagas. O adaptador remove variáveis de API Google herdadas, usa `--mode plan` no Antigravity e `--approval-mode plan` na CLI Gemini. Ferramentas disponíveis ainda dependem das políticas oficiais: modo plan não é isolamento completo do sistema operacional. Não usa bypass de permissões. Falhas de autenticação e execução são exibidas sem persistir URLs de autenticação de stderr. A disponibilidade do adaptador permanece pendente até uma execução bem-sucedida do processo atual; reiniciar o backend exige nova validação em vez de presumir que o login continua válido.

[Headless oficial](https://www.antigravity.google/docs/cli/headless/) descreve o envelope JSON: SUCCESS/response/usage. Sem uso reportado, métricas ficam desconhecidas, sem estimativa inventada. Streaming não é simulado: adaptador JSON publica o resultado quando recebido.

## REA como metodologia

Escolha **REA · Research → Evaluate → Architect** em Nova tarefa ou pela página **REA**. O supervisor faz três chamadas sequenciais ao agente escolhido. Cada etapa concluída é persistida em `task_steps`, produz evento e checkpoint; retomada pula etapas confirmadas. O pacote de continuidade inclui as etapas com suas saídas. Etapas malsucedidas não são marcadas como concluídas. Custo: até três chamadas por execução completa, além de eventuais retomadas.

O fluxo instrui o agente a separar observado, inferido e desconhecido; pesquisar fontes verificáveis; comparar alternativas e produzir arquitetura. Não garante que uma fonte esteja correta ou que o agente tenha navegado. Fontes e resultados exigem revisão. Não executa implementação automaticamente após arquitetura; as políticas read-only continuam.

## REA como motor Reverse Engineer Anything

Instalado `rea-agents` 6.7.0 localmente, sem registrar MCP global nem substituir skills pessoais. Pela página REA → **Analisar artefato**, selecione o projeto e o alvo. Operações expostas por allowlist:

- JavaScript/Electron/ASAR: `analyze-javascript-application`.
- Mach-O/app macOS: `inspect-macho`.
- ELF/objeto Linux: `inspect-binary-layout`.

O caminho é resolvido e precisa existir dentro do projeto registrado, inclusive após symlinks. Não há comandos arbitrários, execução do alvo, instalação de motores nativos ou endpoints de instrumentação. Para um artefato fora do projeto, registre explicitamente seu diretório em Settings. Análise estática não comprova comportamento em runtime.

O motor retorna Evidence JSON integral como resultado e evento `rea_evidence`; IDs e limitações originais são preservados. Erros e limites da ferramenta não viram conclusão bem-sucedida. Limite de saída: 8 MiB; resultados maiores são rejeitados com aviso em vez de truncados silenciosamente. Análises nativas podem exigir motores adicionais não instalados automaticamente.

Foi realizada análise real do motor em um **artefato sintético de teste** (`tests/fixtures/rea-app`), sem LLM e sem cota. Evidência bruta em `evidence/rea-engine-smoke.json`. A primeira tentativa falhou por restrição de cache de compilação Swift no sandbox do ambiente; a repetição autorizada com cache padrão passou. Isso valida a integração JavaScript, não todos os provedores nativos.

## Segurança e pendências

A confiança persistente solicitada pelo Antigravity autoriza sua CLI a ler, editar e executar no diretório. É uma decisão separada de autenticar a conta; não é confirmada sem autorização explícita do usuário. O orquestrador continua solicitando modo plan.

Failover automático permanece desabilitado. Não há promessa de equivalência entre provedores ou de economia de tokens. A suíte contém testes de migração de banco, parsing dos protocolos, preservação de etapas e rejeição de caminhos fora do projeto.

## Resultado verificado nesta instalação

O usuário autorizou explicitamente confiar **somente** em `/Users/guilherme/Documents/ai-orchestrator`. A confiança foi confirmada no fluxo oficial. O compartilhamento opcional de interações para melhoria do produto foi desativado no onboarding.

A chamada real **HTTP → supervisor → Antigravity → Gemini → SQLite** retornou `GEMINI_ORCHESTRATOR_OK`, estado completed, sem ferramentas solicitadas. Uso reportado: 6952 input, 2191 output, 2181 thinking, total 9143, cached 0. Thinking já integra os valores do provedor; não somar novamente ao total. Evidência com checkpoint: `evidence/google-e2e.json`. Isso comprova a chamada mínima e a persistência, não failover ou disponibilidade permanente.

O REA depende de Zod 4.4.3 na distribuição original; `npm audit` identificou GHSA-mrhx-c7xc-m3w5. Foi aplicado override local para Zod 4.6.6 e o audit da instalação retornou zero vulnerabilidades. Análise real do artefato sintético foi repetida após a correção. Motores nativos opcionais não foram instalados ou ativados.
