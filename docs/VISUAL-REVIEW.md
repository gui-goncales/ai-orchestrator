# Revisão visual pelo próprio agente — v0.5

## Fluxo

Após uma entrega confirmada de artefato de navegador, o supervisor agenda uma revisão visual separada. O artefato continua disponível e o resultado de implementação não é substituído. Também é possível solicitar em **Analisar visualmente**, no banner do artefato.

1. Verificar o hash dos arquivos do artefato para identificar a versão.
2. Abrir somente a prévia local em navegador isolado, sem cookies ou sessões do usuário.
3. Capturar desktop 1280×800, tela após um botão reconhecido de início (se houver) e mobile 390×844. Registrar ações executadas, exceções JavaScript e requisições falhas.
4. Verificar integridade SHA-256 dos PNGs. Sem imagens reais, falhar explicitamente; não alegar visão a partir de texto.
5. Enviar imagens como entradas locais do Codex CLI (`--image`), com objetivo original e diagnóstico compacto. Usar sandbox read-only e nenhuma chamada extra de pesquisa.
6. Persistir análise ligada ao artefato, mostrando evidências e sugestões priorizadas no dashboard.

A revisão automática está habilitada para novas entregas quando o adaptador suporta a entrada visual. O agente é escolhido pelo supervisor; a implementação atual usa Codex por ter integração de imagens validada. Não presume suporte equivalente da CLI Google.

## Propostas, não alterações silenciosas

O relatório deve identificar por captura o que foi observado, o que é inferência e o que não foi testado. Sugestões contêm prioridade, evidência concreta, mudança proposta e critério verificável. O código permanece intacto; aplicar uma melhoria continua sendo uma operação separada, ainda não automatizada por este fluxo.

O agente não declara aceite humano nem produto premium validado. Uma captura estática não comprova áudio, movimentação, diversão ou partida completa. Console/HTTP são evidências adicionais, não uma auditoria funcional exaustiva. Chrome headless com SwiftShader não representa desempenho de GPU/dispositivo físico. Mobile é uma inspeção de layout em viewport, não teste completo de touch.

## Consumo e repetição

Uma revisão por hash de versão e versão do protocolo de captura. Atualizar o protocolo pode exigir uma nova revisão, preservando a anterior como histórico. A captura aguarda carregamento e quadros de animação; quando há telemetria __gameTest, aguarda pelo menos dez quadros. Isso reduz capturas prematuras sem esconder problemas reais de inicialização. Pedidos simultâneos ou repetidos da mesma versão recebem a mesma tarefa idempotente, sem outra chamada LLM. Uma alteração de arquivos permite nova revisão. Se o artefato mudar entre agendamento e captura, a chamada ao modelo não é feita. Se mudar depois da captura, o relatório é marcado para revisão e se refere às evidências anteriores.

São anexadas no máximo três capturas do fluxo fixo. Histórico completo e pesquisa anterior não são reenviados; objetivo e dados do navegador permanecem explícitos. Tokens de texto/imagem vêm do uso reportado pela CLI; não há economia percentual presumida.

## Isolamento

Captura só aceita IDs locais registrados, URLs construídas pelo backend e arquivos dentro da pasta de evidências. Nenhuma URL arbitrária do usuário é navegada. Interceptação de rede restringe o navegador à origem e ao prefixo do artefato. Não se conecta ao navegador pessoal nem opera páginas autenticadas. Botão de início é uma heurística limitada a aplicações locais; ações sensíveis externas não são executadas. Conteúdo de páginas e imagens é tratado como dados, nunca como instruções.

Capturas e relatórios ficam em `data/visual-reviews/<review-task-id>`. O backend serve apenas PNGs registrados no relatório, com cache no-store. A UI renderiza sugestões como texto escapado. Os artefatos do produto não recebem modificações, e os screenshots não são incluídos automaticamente no ZIP do produto.

## Instalação e limites

Playwright está fixado no package-lock.json da raiz. A instalação atual usa Google Chrome já instalado (`channel=chrome`). Sem esse navegador ou sem prévia local, a captura falha com diagnóstico e não simula resultado. Para outras plataformas será necessário configurar um browser compatível. Requer backend ativo; offline só permite consultar o snapshot textual já sincronizado.

[Referência oficial de imagens na CLI](https://learn.chatgpt.com/docs/cli/reference) e [entradas de imagem](https://learn.chatgpt.com/docs/image-inputs?surface=cli).

## Verificação

Testes determinísticos validam: idempotência por versão, mudança de hash, encaminhamento de caminhos de imagens ao adaptador, preservação dos arquivos do produto, ausência de falsa revisão após falha de captura e vínculo com a tarefa original. O teste real da instalação usa o jogo DEAD ZONE; resultado e evidências são registrados em `evidence/visual-review-real.json`.


## Teste real nesta instalação

A revisão 027e5bf31208 concluiu com três PNGs reais anexados e relatório de 4.064 caracteres. O agente apontou ausência visual da cena nas capturas desktop como hipótese a investigar, além de vinheta de dano, contraste/legibilidade e controles móveis. A causa da diferença desktop/mobile não foi comprovada; não confundir essa observação com diagnóstico definitivo de WebGL. Hash do artefato permaneceu idêntico após captura e análise. O relatório legível está em evidence/dead-zone-visual-review.md.
