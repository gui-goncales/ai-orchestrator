# AI Orchestrator: do gerenciamento de agentes à execução do trabalho

Pesquisa e proposta de produto — 27/10/2026.

Continuação: [investigação REA e plano de execução](REA-STRATEGY-EXECUTION-PLAN.md), com dez cenários registrados, limites de acesso, decisões técnicas, incrementos e backlog de PRs. A pesquisa original abaixo foi documental; o uso posterior de REA está separado nessa continuação.

## Decisão proposta

Construir um ambiente que transforma solicitações, documentos e dados em entregas profissionais editáveis, conectadas ao trabalho de uma equipe. A pessoa informa o resultado; o sistema organiza contexto, execução, revisão e entrega. Orquestrar modelos é uma capacidade interna, não a proposta de valor principal.

Visão ampla, entrada focada: começar por operações de clientes e produção de conteúdo em equipes de serviços, atendendo account managers, copywriters e designers no mesmo fluxo. Essa é uma hipótese de mercado, não uma demanda já validada. Expandir para outras funções quando o mecanismo se provar reutilizável.

## Método e limites

- Inspeção do README, documentação de arquitetura, implementação e entregas, e código atual em backend/core.py, backend/agent_engine.py, backend/artifacts.py, backend/revisions.py e componentes do chat.
- Pesquisa documental em fontes oficiais de Lovable, Asana, Gamma, Canva, Zapier e Atlassian. As páginas são mutáveis; as observações refletem a consulta nesta data.
- Não foram realizadas entrevistas, testes comparativos práticos dos concorrentes ou medições de produtividade. Funcionalidades documentadas não comprovam facilidade real ou confiabilidade.
- REA não foi necessário nesta etapa: as perguntas eram sobre produto e capacidades publicamente documentadas, e o código do AI Orchestrator está disponível. Não há inferência sobre arquitetura privada dos concorrentes.
- As tarefas profissionais abaixo são hipóteses para descoberta. Não representam pesquisa primária com esses profissionais.

## 1. O problema é a distância entre pedir e concluir

Um profissional precisa descobrir informações, interpretar um pedido incompleto, produzir algo, revisar com outras pessoas e registrar ou entregar o resultado. Um chat que escreve uma resposta cobre apenas parte dessa sequência.

A pesquisa State of Teams 2025 da Atlassian, com 12 mil trabalhadores do conhecimento e 200 executivos, relata que 25% do tempo é gasto procurando respostas. É um sinal de problema de contexto, com amostra e interesse comercial próprios; não prova demanda pelo nosso produto. [Fonte](https://www.atlassian.com/blog/state-of-teams-2025).

Problemas a investigar:

1. O material existe, mas está espalhado entre documentos, mensagens e planilhas.
2. O pedido chega incompleto, e alguém precisa transformá-lo em trabalho executável.
3. A IA cria texto genérico porque desconhece o cliente, a marca e as decisões anteriores.
4. A entrega precisa ser remontada manualmente em outra ferramenta.
5. Alterações de uma pessoa não chegam às demais entregas relacionadas.
6. Aprovações e responsabilidades se perdem em conversas.
7. Não fica claro se algo foi somente sugerido, criado, validado ou enviado.

## 2. O que aprender com os produtos pesquisados

| Produto | Capacidade documentada | Princípio a aproveitar | Limite da comparação |
| --- | --- | --- | --- |
| Lovable | Planeja, modifica o projeto, verifica e permite publicar uma versão hospedada | Assumir a execução até um resultado utilizável | Seu objeto central é uma aplicação; não demonstra domínio de todas as profissões |
| Asana AI Studio | Fluxos com gatilhos, condições, ações e instruções em linguagem natural | IA deve operar sobre trabalho estruturado e processos repetíveis | Configurar um fluxo ainda pode exigir aprendizado |
| Gamma | Geração, colagem ou importação de material, edição e exportação | Começar do material existente e entregar em formato aproveitável | Importação e exportação têm limitações de fidelidade e formato |
| Canva | Brand Kits, templates e controles de aprovação | Contexto de marca e padrões compartilhados fazem parte da produção | Recursos e permissões variam por plano |
| Zapier | Aprovação antes do uso de ferramentas na evolução para AI by Zapier | Autoridade para agir deve existir no executor | Conexões e automações precisam de configuração e manutenção |

Fontes: [Lovable Build](https://docs.lovable.dev/features/agent-mode), [Plan](https://docs.lovable.dev/features/plan-mode), [publicação](https://docs.lovable.dev/features/publish), [Asana AI Studio](https://help.asana.com/s/article/ai-studio), [Gamma importação](https://help.gamma.app/en/articles/11047840-how-can-i-import-slides-or-content-into-gamma), [Gamma exportação](https://help.gamma.app/en/articles/8022861-what-s-the-easiest-way-to-export-my-gamma), [Canva Brand Kit](https://www.canva.com/help/brand-kit/), [Canva aprovações](https://www.canva.com/en_in/help/manage-approval-settings-for-teams/), [Zapier migração e aprovação](https://help.zapier.com/hc/en-us/articles/47402591569805-Migrating-from-Agents-to-AI-by-Zapier).

Minha interpretação: a facilidade do Lovable está relacionada à compressão de uma cadeia operacional. O usuário consegue pedir, ver e ajustar um produto porque o sistema assume várias decisões de execução. A documentação sustenta a existência dessa cadeia; estabelecer por que usuários a consideram fácil exige observação de uso.

O equivalente para o AI Orchestrator é completar ciclos de trabalho, com objetos diferentes de software: um briefing, uma proposta, uma apresentação, uma planilha ou um conjunto de peças.

## 3. Tarefas concretas por perfil

| Perfil | Situação real a investigar | Entrada | Entrega e ação | Critério de qualidade |
| --- | --- | --- | --- | --- |
| Account manager | Preparar reunião de acompanhamento | Histórico autorizado, notas, cronograma e indicadores | Pauta, riscos, pendências e rascunho de atualização | Cada compromisso tem fonte, responsável e prazo; dados ausentes ficam explícitos |
| Copywriter | Produzir campanha coerente | Briefing, público, oferta, referências e guia de voz | Documento editável com variantes por canal | Cobertura do briefing, limites por canal e alegações verificáveis |
| Designer | Transformar pedido em produção | Briefing aprovado, assets e templates | Direções visuais, peças e adaptações em formatos compatíveis | Dimensões, legibilidade, assets corretos e revisão humana de direção |
| Comercial | Preparar proposta | Descoberta, catálogo e preços autorizados | Proposta editável e rascunho de atualização do CRM | Escopo e valores conferidos, descontos dentro da autorização |
| Operações | Consolidar informações recorrentes | CSVs, planilhas e regras de negócio | Planilha reconciliada, exceções e relatório | Totais conferidos, fórmulas auditáveis e origem dos números |
| Gestor | Entender avanço e destravar equipe | Entregas, prazos, dependências e decisões | Resumo com evidências e prioridades propostas | Distingue fato, estimativa e recomendação |

Não criar seis chats com personas diferentes. Reutilizar capacidades de leitura, transformação, produção, revisão e entrega. O perfil oferece atalhos e critérios adequados; a pessoa pode realizar tarefas de qualquer área.

## 4. Modelo do produto

### A. Um espaço de trabalho por contexto

Empresa → cliente ou iniciativa → solicitações → entregas e decisões. Uma pasta local pode ser vinculada, mas não deve ser obrigatória. Um freelancer também deve trabalhar sozinho, sem montar uma organização.

Cada contexto reúne fontes autorizadas, guia de marca, público, referências aprovadas, responsáveis e decisões. Toda informação recuperada precisa manter origem e data. Separar contexto de clientes; permitir corrigir e revogar memórias. Uma decisão antiga pode ter sido substituída.

### B. Solicitação como compromisso de entrega

Ao receber “preciso apresentar os resultados do cliente”, o sistema identifica o cliente e os materiais disponíveis, propõe a entrega e pergunta apenas o que impede continuar. Não exige que a pessoa escolha um agente ou construa um fluxo.

Internamente registrar objetivo, entradas, restrições, entregáveis, destino, critérios de aceite, dependências e autoridade para agir. Mostrar uma versão curta: “Vou montar uma apresentação com os dados de setembro, destacar riscos e preparar o e-mail para revisão”.

### C. Entregas como objetos editáveis

Documento, planilha, apresentação, imagem, conjunto de conteúdo e aplicação web devem ter representação, edição, versões e validação próprias. Um HTML que imita slides não equivale a uma apresentação editável.

Permitir selecionar um trecho ou item e pedir ajustes sem regenerar tudo. Manter autoria humana e registrar o que mudou. Não sobrescrever manualmente o trabalho de outra pessoa durante uma revisão automática.

### D. Fluxos que operam nas ferramentas existentes

Priorizar uma integração de documentos compartilhados e uma de acompanhamento de trabalho conforme a descoberta com usuários. Cada conector declara exatamente o que lê, cria, altera e envia. A presença de um conector no ambiente de desenvolvimento não significa que ele exista no produto distribuído.

Importar e exportar arquivos é uma entrada útil, mas não substitui sincronização. APIs oficiais primeiro. Automação de navegador somente quando necessária, com manutenção e falhas explícitas.

### E. Revisão, colaboração e continuidade

Responsável, revisor, prazo, comentário e versão aprovada devem pertencer à entrega. Aprovar uma versão não aprova mudanças futuras. Revisões de escopo mostram impacto em entregas dependentes e propõem alterações para revisão.

Exemplo: mudar a oferta aprovada sinaliza os anúncios e a apresentação afetados. O sistema não publica automaticamente todas as alterações em cadeia.

### F. Rotinas reutilizáveis

Depois de um fluxo bem-sucedido, permitir “repetir para outro cliente” ou “preparar toda segunda-feira”. Salvar estrutura, critérios e fontes permitidas, sem copiar dados privados entre clientes. A execução recorrente exige agendador persistente, deduplicação e tratamento de falhas, não apenas um prompt salvo.

## 5. Experiência completa de referência

Pedido: “Prepare a reunião mensal do cliente Aurora e os materiais da campanha de novembro”.

1. A pessoa seleciona Aurora e anexa ou conecta o material. O sistema identifica fontes, períodos e lacunas.
2. Propõe um conjunto de entregas: resumo do mês, pauta, briefing e rascunhos da campanha. Se o objetivo estiver amplo demais, combina primeiro o escopo.
3. Detecta conflito de datas entre briefing e cronograma. Faz uma pergunta objetiva e continua trabalhos independentes.
4. Consolida indicadores em uma planilha com origem e cálculos. Sem acesso aos indicadores, produz uma estrutura marcada como incompleta; não inventa resultados.
5. Gera apresentação e documento de conteúdo editáveis. Mostra quais informações sustentam os números e as alegações.
6. O account ajusta prioridades. O copy revisa as mensagens. O designer recebe conteúdo aprovado, assets e formatos, preservando as decisões já tomadas.
7. Uma mudança de oferta sinaliza dependências. Alterações propostas aparecem antes/depois e passam por revisão.
8. A pessoa aprova uma versão. O sistema salva no destino conectado; enviar ao cliente ou publicar exige autorização compatível com a ação.
9. O fluxo pode ser repetido no mês seguinte usando novas fontes, mantendo os critérios e sem reaproveitar números antigos como atuais.

Esse fluxo é uma visão futura, não uma capacidade já entregue.

## 6. Distância para a implementação atual

| Evidência no repositório | Valor aproveitável | Evolução necessária |
| --- | --- | --- |
| Store em backend/core.py: projetos com name/path, tarefas, memória, eventos e checkpoints | Persistência e rastreabilidade | Contextos sem pasta obrigatória, organização, membros e permissões |
| WorkspaceTools em backend/agent_engine.py | Operações locais de arquivos e comandos | Extração e edição por formato; ferramentas remotas com permissões e resultados estruturados |
| backend/artifacts.py exige index.html e JavaScript na validação | Entrega web com inventário e prévia | Registro de tipos de artefato e validadores próprios; documento não deve falhar por não ter JavaScript |
| backend/revisions.py e revisão visual | Base para comparar e revisar versões web | Versões independentes de tarefa, comentários e aceite por versão |
| Roteamento, adaptadores e recuperação | Infraestrutura de execução reaproveitável | Planejamento por resultado, capacidades e critérios de entrega |

A documentação contém descrições históricas que já não correspondem a tudo no código: por exemplo, run_command existe atualmente em WorkspaceTools. Planejamento de implementação deve usar código e testes atuais como evidência e reconciliar os documentos.

Não foi feita auditoria exaustiva de cada endpoint. O diagnóstico acima se limita aos componentes inspecionados.

### Separação arquitetural proposta

1. Contexto de negócio: cliente, iniciativa, fontes, decisões e marca.
2. Pedido e entregas: resultado esperado, critérios, dependências e destinos.
3. Execução: adaptadores, ferramentas, orçamento, retomada e validação.
4. Colaboração: pessoas, revisão, autorização e versões.

Entidades candidatas: Workspace, Membership, ClientContext, Source, Brief, Deliverable, DeliverableVersion, Review, Approval, Connection e Run. Task pode continuar representando execução; Deliverable passa a representar o objeto que a pessoa utiliza. O desenho de banco definitivo depende do piloto.

Operações remotas precisam de registro de intenção e confirmação do efeito. Repetir uma execução após queda não pode duplicar e-mails ou registros. Usar chaves de idempotência onde disponíveis e reconciliação quando o destino não as suporta. Permissões e aprovação devem ser verificadas pelo executor, vinculadas à ação e à versão, não apenas escritas no prompt.

O backend local atual exige inicialização e provedores configurados. Para usuários não técnicos, avaliar aplicativo empacotado com atualização e diagnóstico versus serviço hospedado. O modelo hospedado exige autenticação, isolamento entre organizações e gestão de credenciais; expor o servidor local atual não resolve distribuição.

## 7. Priorização por aprendizado

### Etapa 1 — descobrir o trabalho

Recrutar 12 pessoas de pelo menos quatro organizações, distribuídas entre atendimento, conteúdo, design e operações. Meta de amostra exploratória, sem representatividade estatística. Não concentrar participantes na equipe do fundador.

Pedir a demonstração das três últimas tarefas reais, com materiais autorizados: de onde veio o pedido, o que faltou, quantas ferramentas usou, onde revisou, o que entregou e o que precisou refazer. Observar o trabalho atual antes de apresentar a solução.

Comparar preparação de reunião, briefing de campanha e consolidação de relatório em frequência, tempo total, retrabalho, acesso a dados e disposição de adoção. Escolher o fluxo com evidência mais forte; a recomendação inicial de atendimento + conteúdo pode mudar.

### Etapa 2 — entregar um ciclo completo

Primeiro recorte sugerido: materiais autorizados → briefing estruturado → documento de campanha editável → revisão → exportação DOCX. Deve funcionar com arquivos antes de depender de muitas integrações. Um segundo fluxo, como atualização de cliente a partir de notas, testa se o núcleo se reutiliza.

Construir contexto de cliente sem exigência de pasta, importação dos formatos escolhidos, artefato de documento, edição localizada, histórico e critérios de qualidade. Não chamar isso de colaboração multiusuário enquanto não houver identidade e permissões.

### Etapa 3 — entrar na operação da equipe

Adicionar o destino mais utilizado pelos participantes, revisão por versão, responsáveis e uma integração de acompanhamento. Só então validar rotinas recorrentes e dependências entre entregas.

Design editável avançado e integração Figma/Canva entram conforme evidência e capacidade real das APIs. Não prometer que exportação de PNG resolve a necessidade de editar peças profissionais.

### Etapa 4 — ampliar para outras áreas

Comprovar o mesmo motor em propostas comerciais, relatórios de operações e outras tarefas. Expandir por fluxos que compartilham capacidades, evitando construir uma aplicação diferente para cada profissão.

## 8. Métricas e critérios de decisão

Métrica principal: proporção de tarefas reais cuja entrega é aceita e utilizada no destino esperado, sem reconstrução manual substancial. Registrar como isso foi observado; baixar um arquivo não prova uso.

Medir tempo total incluindo revisão, correções e transporte entre ferramentas; tempo até a primeira entrega útil; número de intervenções; falhas de integração; uso recorrente por contexto; custo por entrega aceita; erros críticos e vazamentos entre contextos.

Metas iniciais para decidir se avançamos, não resultados obtidos: pelo menos 8 de 10 participantes concluem a tarefa piloto sem ajuda operacional do pesquisador; redução mediana de 30% no tempo total em comparação com tarefas equivalentes; nenhum envio sem autorização ou mistura de clientes. Usar avaliação por profissionais do domínio e registrar efeitos de aprendizado. Amostras pequenas orientam produto, não sustentam alegações públicas de ganho generalizado.

Se o produto exige que o pesquisador escreva o prompt, reconstrua a entrega ou conserte a integração, a tarefa não conta como conclusão autônoma.

## 9. Diferenciação a testar

“Descreva o trabalho. Receba a entrega no contexto certo, pronta para revisar e continuar.”

A vantagem potencial está em preservar contexto e decisões ao atravessar documentos, pessoas e ferramentas. Seleção de modelos e memória são meios. Sem formatos úteis, integração e qualidade verificável, o produto continua sendo uma camada de conversa.

Evitar um catálogo gigantesco de agentes, um editor completo para cada profissão e um construtor de automações obrigatório no primeiro uso. Começar resolvendo bem um ciclo frequente e expandir o núcleo comprovado.

## 10. Prompt estratégico consolidado

Atue como pesquisador de produto e arquiteto de software para evoluir o AI Orchestrator em um ambiente de execução de trabalho para profissionais técnicos e não técnicos. A proposta precisa abranger funções reais do dia a dia: reunir contexto, interpretar solicitações, produzir entregas editáveis, revisar com pessoas e concluir ações nas ferramentas utilizadas pela equipe.

Não restrinja a solução a comunicação, interface, onboarding, personas de agentes ou templates de prompts. Investigue quais capacidades operacionais eliminam trabalho manual. Use o Lovable como referência de execução integrada entre intenção e resultado, e compare princípios de produtos como Asana, Gamma, Canva e Zapier, sem copiar indiscriminadamente suas interfaces.

Inspecione o código atual antes de propor mudanças. Separe capacidades verificadas, limitações, hipóteses e visão futura. Consulte fontes oficiais atualizadas; use REA somente quando houver uma pergunta concreta que exija evidência de comportamento ou de artefatos indisponível na documentação. Não presuma acesso à arquitetura privada de concorrentes.

Mapeie tarefas recorrentes de account managers, copywriters, designers e outros perfis. Para cada tarefa, especifique gatilho, entradas, decisões humanas, ferramentas, saída editável, destino, frequência, custo de erro e critério de sucesso. Procure mecanismos comuns e valide-os com pessoas de organizações distintas; não generalize as necessidades do fundador.

Recomende um segmento inicial e até dois fluxos completos para validar. Explique como o núcleo permitirá ampliar o produto sem criar sistemas independentes por profissão. Detalhe contexto de clientes, fontes e atualização, tipos de entregas, edição e versões, revisão, integrações, permissões, retomada e prevenção de ações duplicadas. Inclua a forma de instalação ou acesso para quem não usa terminal.

Entregue uma comparação com evidências, uma tese de produto, exemplos completos de uso, análise da distância para o código atual, prioridades por dependência e um plano de descoberta e piloto com métricas de qualidade, tempo total e uso real. Identifique o que deve ser construído, integrado ou adiado. Trate metas como hipóteses e só declare melhorias comprovadas após medi-las. Nesta etapa produza pesquisa e especificação; mudanças de implementação devem seguir um recorte definido a partir dos achados.
