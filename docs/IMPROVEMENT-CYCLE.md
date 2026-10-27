# Ciclo de melhoria e versões — v0.6

## Uso no dashboard

1. Abra a revisão visual concluída de um artefato.
2. Marque as propostas desejadas e/ou escreva feedback em **Ajustes adicionais**.
3. Clique **Aplicar em nova versão**. O supervisor escolhe um agente capaz de editar e cria uma candidata em outra pasta.
4. Acompanhe validação, novas capturas e análise. Compare **Antes** e **Depois**, confira os arquivos modificados e abra a candidata.
5. Clique **Usar esta versão** para mudar o resultado ativo do artefato original.
6. Se necessário, clique **Restaurar versão anterior**. Os arquivos da candidata e da versão anterior continuam preservados.

O ciclo não repete REA. Reenvia apenas propostas/feedback, imagens relevantes e referência aos requisitos já salvos. Não publica externamente e não muda automaticamente o resultado ativo. Aceite de qualidade e promoção de versão são ações distintas.

## Versões e segurança

Cada revisão tem um task_id próprio e uma cópia completa do artefato em artifacts/<revision-id>. A versão base permanece no mesmo diretório, com hash registrado. A cópia inicial usa staging e renomeação para evitar tratar snapshot parcial como versão íntegra.

Edição usa Codex CLI em sandbox workspace-write, com diretório de trabalho exclusivo da candidata. Imagens anteriores são anexadas e validadas por SHA-256. vendor/ e planning/ são protegidos também pela validação do diff. A proposta não autoriza mudar outros projetos, dependências, credenciais ou fazer publicação.

Validação inclui entrada HTML, JS de aplicação, parsing Node e integridade do original. O backend não executa scripts npm gerados. Depois, o navegador captura a candidata e registra erros/requisições falhas. O agente recebe imagens DEPOIS e referências ANTES relacionadas às propostas, além dos critérios, e deve distinguir atendido, parcial, não atendido e não verificável.

**Pronta** significa disponível para revisão humana, não qualidade garantida. Testes sintáticos e capturas de poucos estados não comprovam partida completa, FPS, áudio, instalação PWA ou diversão. A promoção exige validação estrutural e revisão visual concluídas sem erros de página ou requisições falhas; ainda depende do aceite explícito do usuário.

## Persistência e recuperação

Tabela revisions registra base, hash, tarefa, revisão de origem, diff, validação e análise posterior. Artefatos mantêm apontamento para a versão ativa. Aceitar/restaurar troca esse apontamento em transação SQLite, gera evento e checkpoint com manifesto; nunca apaga pastas.

Propostas de versões antigas, candidatas alteradas após validação e snapshots modificados são recusados. Mesma seleção e feedback na mesma base reutilizam a tarefa idempotente. Uma seleção diferente cria outra candidata. Falhas ou cancelamento não promovem código. Retomada conserva a candidata e não repete uma etapa de edição já confirmada apenas para validá-la novamente.

Aceitar é bloqueado enquanto há execução ativa ou enquanto a revisão posterior não terminou. Restauração se aplica à candidata atualmente ativa; não substitui uma versão mais recente silenciosamente. As URLs antigas permanecem disponíveis como versões históricas, enquanto o botão principal e o ZIP do artefato original seguem o apontamento ativo.

## Limitações atuais

Propostas são extraídas de tabelas de prioridades P1/P2/P3 do relatório. Quando a análise não tem tabela estruturada, o feedback livre continua disponível. A captura é de navegador local em contexto isolado, e o aceite de uma versão continua humano. Não há loop ilimitado de autoedição nem estimativa inventada de ganho de qualidade/tokens.


## Validação desta instalação

72 testes automatizados do projeto passaram, incluindo criação idempotente, seleção de propostas, rejeição de versão antiga, edição isolada, validação de arquivos protegidos, aceite, checkpoint, restauração e reaceite. A candidata real cd3726aca860 alterou apenas main.js, style.css e QA_REPORT.md, preservando o hash da base. Os nove testes de simulação do jogo também passaram. A análise e369bfbeb3fe recebeu capturas posteriores e referência anterior e classificou a redução da vinheta como atendida, sem afirmar validação de dano ou partida completa. Evidências em evidence/revision-comparison-real.json e evidence/revision-cycle-final.json.
