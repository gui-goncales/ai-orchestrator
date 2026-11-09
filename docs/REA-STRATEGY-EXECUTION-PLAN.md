# Evolução técnica e estratégica do AI Orchestrator

Plano de execução baseado em inspeção REA e código — 27/10/2026.

Status: plano executável; nenhuma funcionalidade deste documento foi implementada nesta pesquisa. Complementa PRODUCT-DISCOVERY-NONTECHNICAL.md. Estimativas são faixas de planejamento, não compromissos de calendário.

## 1. O que a investigação REA efetivamente estabeleceu

Foram executados dez cenários REA com Chrome em perfil temporário sem sessão, armazenamento vazio, captura de acessibilidade/URL e erros de página. O primeiro cenário incluiu DOM. Ações: navegar até a URL e aguardar a renderização por 1,5–2,5 segundos. Não houve login, geração paga, criação de projeto, envio de mensagens ou publicação. Cada processo iniciado pela captura foi encerrado pelo provedor REA.

Bundle integral: `evidence/rea-product-strategy-2026-10-27.json`, dez registros. Os identificadores abaixo permitem verificar as observações. O campo `unknowns: 0` do exportador apenas indica que não foram criados registros formais de unknown; não significa ausência de dúvidas. As dúvidas estão explicitadas neste plano.

| Alvo | URL solicitada | Evidência REA | Observação e limite |
| --- | --- | --- | --- |
| Lovable app | https://lovable.dev | ev_e2c0e21cf555241561042a289671af16c6e7424f35a230309058723bcca7f56f | Verificação de acesso; não foi possível observar o editor |
| Asana app | https://app.asana.com/ | ev_e386c83289ff3ababadd77b361492f8b9e02f163eb57847465dfea9c35a4aed5 | Redirecionamento para login; não foi possível observar tarefas ou AI Studio |
| Gamma app | https://gamma.app/ | ev_5b41cdc6ea01ebaf2c79211d713b0aa9dd16c9c89ce6b6635418cc7cb0858816 | Tela de espera/verificação; não foi possível observar geração |
| Canva app | https://www.canva.com/ | ev_417c723700aa5e700b4cd3be68bd8f9901a23cac3136738e101afbe85e2cee81 | Página de impedimento com referência à ajuda Cloudflare; não foi possível observar design |
| Zapier app | https://zapier.com/app/login | ev_6baf177a0dc5f8227c6fafbf2273b165ee59bfa8b94c9ddcd4a950d9a5ade0d5 | Login, SSO e e-mail; não foi possível observar automações |
| Lovable docs | https://docs.lovable.dev/features/agent-mode | ev_db175829f6bf5891304852c229aafa6f067e6cdcf866ddb2fd0bdf2cb85af2d5 | Documento público renderizado sobre execução e verificação; não é teste da implementação |
| Asana docs | https://developers.asana.com/docs/webhooks-guide | ev_cc00eb3ca47c25aa27d58d613221275bf9a03ac1c1278e8785aec53ee50712a7 | Documento público renderizado sobre eventos e sincronização |
| Gamma docs | https://developers.gamma.app/ | ev_74065890a13e61d4660cc0036f1007371832d49fca94275d4430b37a2b63b81c | Documento público renderizado sobre geração, edição, exportação, API e MCP |
| Canva docs | https://www.canva.dev/docs/connect/autofill-guide/ | ev_221a8afef60ea91e4a1e4483a3c7d7d154c0b6de512ef95f985fc013a2c7610b | Redireciona ao guia atual de REST APIs; descreve template, job e edição |
| Zapier docs | https://docs.zapier.com/powered-by-zapier/introduction | ev_c11804534c1d0209a16a9259c35e2af1ee507864bd310fe009c359b13739d2bc | Redireciona a Powered by Zapier; descreve alternativas de incorporação |

Captura completa é completude dentro daquele cenário, não cobertura completa de um produto. A espera finita também limita conclusões sobre disponibilidade. Não foram inspecionados bundles privados, servidores, endpoints autenticados ou credenciais. As interfaces de login e verificação não sustentam conclusões sobre a facilidade dos fluxos internos.

### Achados que mudam o plano

**Lovable — execução com escopo e verificação.** A página renderizada descreve implementação direta e ferramentas de verificação, mas ressalva que a maioria das ferramentas de teste roda quando solicitada. Portanto, não assumir “IA gerou” como sinônimo de “resultado testado”. No Orchestrator, cada tipo de entrega terá verificações explícitas e evidências, com qualidade humana separada de validade estrutural. [Documento](https://docs.lovable.dev/features/agent-mode).

**Asana — sincronizar exige mais que receber eventos.** O guia descreve necessidade de endpoint público para webhooks e recomenda consulta de reconciliação quando perder eventos for inaceitável. Decisão: o piloto local usa consulta incremental/manual; webhooks ficam para um serviço preparado para recebê-los. Não expor o backend atual para habilitar essa capacidade. [Documento](https://developers.asana.com/docs/webhooks-guide).

**Gamma — geração não é um comando síncrono de texto.** A superfície pública apresenta criação, consulta de estado, edição e exportação, com autenticação por conta e diferentes famílias de geração. Decisão: contrato de operações remotas com ID, estado e reconciliação; integração Gamma é opcional e condicionada a teste real de formato e custo. Não congelar a arquitetura em um endpoint antigo. [Documento](https://developers.gamma.app/).

**Canva — partir de templates aprovados preserva a continuidade do designer.** O guia descreve descoberta de campos, criação assíncrona por autofill e retorno ao editor. Decisão: testar produção a partir de um template aprovado, mantendo a edição no Canva. Não tentar implementar um editor de design completo no MVP. Elegibilidade, permissões e APIs precisam ser verificadas na conta do piloto. [Documento](https://www.canva.dev/docs/apps/rest-apis/autofill-guide/).

**Zapier — incorporar automação é uma alternativa a manter dezenas de conectores.** A documentação apresenta formas de integrar fluxos e ações com autenticação gerenciada. Decisão: fazer avaliação comercial e técnica antes de assumir que o acesso, a distribuição e a economia servem ao produto. O núcleo não dependerá de Zapier para produzir e revisar documentos. [Documento](https://docs.zapier.com/powered-by-zapier).

Todas essas descrições de capacidades continuam sendo alegações documentais, ainda que a renderização tenha sido observada por REA. Requisições API não foram executadas. As decisões arquiteturais são nossas inferências.

## 2. Direção estratégica e recorte

Promessa proposta: transformar material e solicitações dispersas em entregas revisáveis, no contexto correto e no destino útil.

Entrada de mercado a testar: equipes de serviços e marketing, incluindo agências e equipes internas. Três perfis colaboram sobre um mesmo trabalho: atendimento organiza compromissos, conteúdo produz mensagens, design prepara peças. A profissão muda os atalhos e critérios; não limita as capacidades disponíveis.

Primeiro resultado: uma pessoa transforma notas e materiais em um briefing e um documento de conteúdo, edita partes, aprova uma versão e exporta DOCX. Segundo resultado: um account transforma notas em atualização de cliente com responsáveis e prazos. Isso testa reutilização do núcleo entre funções antes de ampliar integrações.

Terceiro resultado, condicionado à prova de conceito: conteúdo aprovado preenche um template de design e abre uma peça editável no Canva. Apresentação via Gamma é opção posterior, se os usuários realmente priorizarem esse formato.

O diferencial a provar é a redução do trabalho de juntar contexto, remontar entregas e coordenar revisões. Um catálogo de modelos ou agentes não comprova essa redução.

## 3. Base atual e pontos de mudança

Inspeção do código da árvore de trabalho, que já contém alterações de outras atividades. Nenhuma delas foi revertida ou modificada neste trabalho.

| Componente atual | Evidência | Mudança planejada |
| --- | --- | --- |
| Store e execução | backend/core.py:83; tabelas projects, tasks, memory, events, checkpoints, artifacts e tool_actions | Migrações aditivas e novos objetos de trabalho; manter tarefas antigas compatíveis |
| Cadastro vinculado a diretório | backend/server.py, POST /api/projects exige pasta existente | Novo contexto de negócio com vínculo local opcional; não substituir silenciosamente o contrato antigo |
| Roteamento e contexto | backend/policy.py: category, choose e build_context; backend/decision.py: plan_task | Contrato de entregáveis e requisitos de capacidade; classificação textual vira fallback explícito |
| Ferramentas locais | backend/agent_engine.py: WorkspaceTools | Ferramentas de negócio tipadas, entrada validada e resultados referenciáveis |
| Artefatos web | backend/artifacts.py:53 exige HTML e JavaScript | Registro por tipo; manter validação web legada como implementação específica |
| Revisões web | backend/revisions.py clona diretórios e compara inventário | Versão de entrega e aceite próprios; adaptar legado sem confundir ponteiro local com publicação externa |
| Interface | frontend/src/types.ts e components/ChatWorkspace.tsx, ChatView.tsx, ProjectContext.tsx | Espaço de entregas, fontes e decisões com edição contextual |

Antes da implementação, registrar resultados atuais das suítes e distinguir falhas preexistentes. Nesta pesquisa, as suítes não foram executadas: nenhuma alteração de runtime foi proposta como pronta.

## 4. Arquitetura alvo incremental

Preservar React, backend Python, SQLite e execução atual no piloto local. Evitar migração de stack sem necessidade demonstrada. Extrair serviços de domínio para não concentrar novas regras em core.py e server.py.

### Objetos e limites

- BusinessContext: cliente ou iniciativa, independente de diretório; vínculo opcional ao project_id legado.
- Source e SourceVersion: identidade, origem, hash, versão remota, data, contexto, texto extraído e acesso permitido. Documento importado é dado, não instrução operacional.
- WorkRequest: objetivo, contexto, entradas, restrições, entregáveis, destino e critérios de aceite.
- Deliverable e DeliverableVersion: conteúdo estruturado, tipo, hashes e linhagem. Versão aprovada é imutável; edição cria candidata.
- Review e Approval: decisão ligada a versão e revisor; alteração de conteúdo invalida autorização futura para enviar aquela versão modificada.
- Operation: passo executável local ou remoto, estado, tentativas, ID remoto, chave de deduplicação e evidência do efeito.
- Connection: capacidades, escopos, identidade e referência ao segredo; segredo não entra em prompt, log ou SQLite em texto aberto.

No piloto individual, registrar o ator local sem apresentar isso como colaboração multiusuário. Membership, autenticação e controles por organização tornam-se obrigatórios antes de acesso compartilhado.

### Contrato de pedido

Objeto versionado com context_id, source_version_ids, deliverables[{type, purpose, acceptance_checks}], constraints, destination e execution_budget. O planejador pode propor dados; o backend valida e resolve permissões. Campos ausentes não recebem valores inventados. Destino externo desconhecido não autoriza envio.

### Contrato de artefato

Cada tipo registra schema, create, render_preview, validate, export e capabilities. Implementar inicialmente document e adaptar web_app. O documento usa uma árvore de blocos tipada, com IDs estáveis para parágrafos e tabelas. Exportação DOCX deve preservar edição. PDF é representação de distribuição, não substituto da fonte editável.

Cada versão registra sources_used, parent_version_id, content_hash e validation_report. Referências por bloco são propostas; conferir se o trecho realmente sustenta uma alegação continua sendo requisito de avaliação, não efeito automático de ter uma citação.

### Contrato de operação e retomada

Estados: pending → running → waiting_remote / waiting_input / waiting_approval → succeeded / failed / cancelled / outcome_unknown. Versão de entrega tem estados independentes: draft → in_review → approved → delivered, com superseded para versões substituídas.

Registrar intenção antes do efeito externo. Salvar ID remoto assim que disponível. Se houver timeout após a requisição, reconciliar o resultado antes de reenviar. Quando não for possível determinar o efeito, marcar outcome_unknown e pedir resolução. Não prometer execução exatamente uma vez quando o destino não fornece mecanismos suficientes.

### Contrato de conector

Descrever capacidade de leitura/escrita, formatos, limites, custos conhecidos, autenticação, cancelamento suportado e estratégia de reconciliação. Métodos propostos: capabilities, validate_connection, execute, get_status e reconcile; cancel somente quando suportado. A autorização é conferida no executor para cada efeito.

Fluxos recorrentes usam o mesmo contrato de operação e chaves por ocorrência. Interromper a observação de um job remoto não garante seu cancelamento. O produto precisa dizer isso corretamente.

## 5. Plano de execução por incrementos

Capacidade de referência para estimativas: duas pessoas de engenharia, participação parcial de produto/design e disponibilidade de participantes. Faixas incluem desenvolvimento e validação; filas de aprovação de fornecedores e recrutamento podem alongá-las. Os responsáveis abaixo são papéis a atribuir, não pessoas já alocadas.

| ID | Incremento | Dependências | Responsável | Faixa | Saída verificável |
| --- | --- | --- | --- | --- | --- |
| E0 | Linha de base, cenários reais e protocolo de avaliação | Nenhuma | Produto + engenharia | 3–5 dias úteis | Baseline técnica, materiais autorizados e escolha fundamentada de dois fluxos |
| E1 | Contextos de negócio e fontes versionadas | E0 | Backend | 5–8 dias | Pessoa cria cliente sem pasta e importa materiais com origem preservada |
| E2 | Entregáveis tipados e documento editável | E1 | Backend + frontend | 7–12 dias | Documento no produto, ajuste localizado, versão e exportação DOCX |
| E3 | Execução orientada à entrega e validação | E2 | Backend | 5–8 dias | Dois fluxos usam o mesmo contrato e distinguem geração de aceite |
| E4 | Revisão por versão e destino conectado | E2, E3 | Full stack | 5–10 dias | Aprovação concreta e entrega confirmada em um destino escolhido no piloto |
| E5 | Prova de conceito de design e apresentações | E1, contrato de operações | Integrações + designer | 3–5 dias por fornecedor selecionado | Viabilidade ou rejeição documentada com artefato real, custo e limitações |
| E6 | Integração de design escolhida | E4, E5 viável | Full stack | 5–10 dias | Conteúdo aprovado vira peça editável sem perder vínculo com a origem |
| E7 | Distribuição e colaboração | E4, decisão local/hospedado | Plataforma + frontend | Estimar após spike de 2–3 dias | Instalação sem terminal ou acesso autenticado; sem expor servidor local |
| E8 | Rotina recorrente e reconciliação | E4, E7 | Backend | 5–8 dias | Uma rotina real repete sem duplicar efeitos após reinício |

E0 e entrevistas continuam ao longo dos incrementos. E5 pode ocorrer enquanto E3 avança, se houver capacidade. E7 envolve requisitos distintos para aplicativo local e serviço hospedado; não cabe uma estimativa confiável única antes dessa decisão. Não somar a tabela como promessa de data: ela contém ramos opcionais.

### E0 — evidência antes de expansão

Recrutar 12 participantes de pelo menos quatro organizações, incluindo atendimento, conteúdo e design. Observar tarefas recentes sem apresentar a solução primeiro. Selecionar pelo menos dois fluxos com entradas reais autorizadas e formatos de saída utilizados. Medir tempo incluindo busca, revisão e remontagem.

Criar matriz com frequência, dor, disponibilidade de dados, qualidade exigida e disposição para adoção. Avaliar por que a pessoa usaria Orchestrator em vez de pedir diretamente ao chat ou ao editor existente. Se o benefício for apenas gerar texto, revisar o recorte.

Capturar baseline técnica em banco temporário e provedores simulados. Não reiniciar o backend em uso nem migrar banco real para obter essa linha de base.

### E1 — contexto útil

Criar migrações versionadas com backup consistente e rollback de aplicação documentado. Adicionar business_contexts, sources e source_versions em módulos próprios. Começar com TXT/MD e DOCX; PDF textual se for recorrente nos materiais observados. OCR somente se houver demanda e extrator validado.

Upload com limites, nomes seguros e detecção de formato. Extração isolada de execução de conteúdo. Manter arquivo original e proveniência, sinalizar falha ou texto ausente. Revogação de uma fonte impede seu uso em novas execuções; preservar apenas auditoria permitida pela política definida.

Aceite: cliente criado sem diretório; contexto A não recupera conteúdo B; alterações da fonte geram nova versão; formato sem suporte tem erro claro. Anexos não podem mudar permissões operacionais por texto embutido.

### E2 — primeira entrega utilizável

Criar backend/deliverables.py, backend/artifact_types.py e backend/document_artifacts.py como módulos candidatos; nomes finais seguem revisão de implementação. Registry web_app mantém contrato antigo. Registry document valida blocos e exporta DOCX com biblioteca selecionada no projeto, sem depender do runtime do ambiente de desenvolvimento.

Adicionar frontend/src/components/DeliverableWorkspace.tsx e SourcePanel.tsx. Edição por seleção de bloco, atualização com expected_version e conflito explícito. Exportação de uma versão aprovada não pode capturar edição concorrente não aprovada.

Aceite: reabrir após reinício preserva conteúdo; corrigir um parágrafo não altera os demais; DOCX abre editável no software usado pelo piloto; tabelas e referências permanecem legíveis. Validar renderização com exemplos reais. Não exigir HTML/JS para declarar documento estruturalmente válido.

### E3 — dois fluxos, um motor

Introduzir WorkRequest no planejamento, validar esquema e exigir capacidades compatíveis do executor. Agentes produzem conteúdo estruturado; ferramentas determinísticas exportam e verificam. Reaproveitar eventos/checkpoints atuais, sem substituir recuperação segura por uma nova implementação simplificada.

Fluxo A: briefing + conteúdo por canal. Fluxo B: notas → atualização de cliente e compromissos. Datas ambíguas e responsáveis não identificados ficam pendentes. Perguntas bloqueiam somente operações dependentes. Orçamento limita tempo, chamadas e custo; limite atingido não declara sucesso.

Aceite: mesmo núcleo atende ambos; nenhuma alegação de resultado comercial sem fonte; critérios críticos têm falha explícita; tarefas antigas mantêm execução e retomada.

### E4 — revisão e entrega

Criar reviews, approvals, operations e connections. Escolher um destino com base no uso dos participantes, por exemplo Google Docs/Drive; confirmar escopos e comportamento por prova de conceito antes de fixar implementação. OAuth e armazenamento seguro de segredos são requisitos do conector, não uma caixa de texto genérica de credencial.

Aprovação vincula hash, versão, ação e destino. Salvar documento privado e enviar ao cliente são ações diferentes. Não converter aprovação editorial em permissão geral para mensagens. Conflitos com edição remota devem gerar versão ou pedido de resolução, sem sobrescrita silenciosa.

Aceite: expiração de conexão solicita reconexão sem perder entrega; timeout não duplica criação; destinatário alterado invalida autorização de envio; retorno remoto e URL do resultado ficam registrados.

### E5/E6 — expandir formatos com o designer

Canva: confirmar elegibilidade, configurar conexão de teste autorizada, listar um template, consultar campos, preencher com conteúdo fictício, acompanhar job e abrir resultado editável. Testar overflow, acentos e imagem ausente. Não usar dados reais de cliente para o teste técnico inicial.

Gamma, se priorizado: gerar apresentação de conteúdo fictício, acompanhar job, editar, exportar e conferir fidelidade. Comparar custo por entrega aceita e necessidade de correção manual. Preferir template aprovado quando o fluxo exigir consistência.

Zapier: avaliar acesso ao programa/API, autenticação, ação com confirmação, custo, portabilidade e suporte a resultado desconhecido. Só adotar se simplificar a manutenção do conjunto de integrações demandado. Não pressupor que o acesso do usuário a uma conta equivale à autorização de distribuir uma integração.

Asana, se for o destino escolhido: criar tarefa de teste com link da versão e responsável autorizado; consultar atualizações e reconciliar. Para implantação local, consulta evita exigir callback público; hospedado pode adicionar webhooks verificados e deduplicados.

Saída de cada spike: seguir ou descartar, operação real demonstrada, limitações, contratos aplicáveis, formatos, custo observado e evidência. Um fornecedor inviável não bloqueia documento e exportação local.

### E7/E8 — uso por outras pessoas

Decidir distribuição com os participantes. Padrão para piloto individual: aplicativo local empacotado com inicialização, diagnóstico e atualização; validar viabilidade dos provedores no pacote. Trabalho compartilhado requer serviço autenticado e isolamento de organizações; usar diretório local de uma pessoa como armazenamento compartilhado não serve.

Rotina inicial sugerida: preparar atualização semanal para revisão, sem envio automático. Persistir calendário com fuso explícito, ocorrência e operação. Reinício recupera ocorrência pendente; alterações de calendário não recriam ocorrências já concluídas. Notificações devem representar ação necessária ou mudança útil.

## 6. Backlog dos primeiros PRs

| PR proposto | Escopo | Dependência | Demonstração obrigatória |
| --- | --- | --- | --- |
| 01 | Baseline, ADRs de domínio e formato de documento | E0 | Execução existente reproduzível; contratos revisáveis |
| 02 | Migrações e BusinessContext independente de pasta | 01 | Criar cliente e executar análise sem registrar diretório |
| 03 | Upload e SourceVersion para formatos iniciais | 02 | Importar, atualizar e rastrear material sem misturar clientes |
| 04 | Deliverable, Version e registry de tipos | 02 | Documento válido e web_app legado usando validadores distintos |
| 05 | Editor por blocos e exportação DOCX | 03, 04 | Ajuste localizado e arquivo editável com versão identificada |
| 06 | WorkRequest e dois fluxos de negócio | 03, 04, 05 | Briefing/conteúdo e atualização de cliente completos |
| 07 | Operações persistentes e revisão por versão | 06 | Aprovação invalidada por alteração; retomada sem duplicação local |
| 08 | Conector do destino escolhido | 07 + spike | Entrega real autorizada com ID remoto e reconciliação |

Dividir PRs adicionais quando o escopo impedir revisão segura. Criar e publicar PRs não faz parte desta etapa documental.

## 7. Testes e critérios para avançar

Testes automatizados de domínio: segregação de contextos, migração de base anterior, conflito de versão, invalidação de aprovação, extração falha, orçamento esgotado, credencial revogada, job remoto pendente, timeout após efeito e reinício antes da confirmação. Contratos de conectores usam simulação para falhas; separar provas reais autorizadas das simulações.

Testes de aceitação com pessoas: participante importa material, conclui entrega, corrige um trecho e utiliza o resultado sem ajuda operacional do pesquisador. Avaliador da área verifica cobertura, exatidão e retrabalho. Usar tarefas equivalentes e registrar efeitos de aprendizado ao comparar tempo.

Metas propostas para piloto: 8/10 conclusões autônomas, redução mediana de 30% no tempo total e zero mistura de clientes ou envio sem autorização. Não são resultados obtidos nem prova estatística. Se a qualidade cair ou a revisão consumir a economia, não ampliar o catálogo.

Métrica principal: entregas aceitas e utilizadas por contexto por semana. Acompanhar custo por entrega aceita, tempo de revisão, alterações manuais, repetição semanal e falhas por tipo. Tokens e quantidade de agentes são diagnósticos internos.

Critérios de expansão: segundo fluxo reutiliza o núcleo; usuários de organizações diferentes retornam sem acompanhamento; o formato de saída serve ao destino; a equipe consegue explicar e recuperar falhas. Se só o fundador consegue operar, investigar antes de adicionar funcionalidades.

## 8. Pendências de evidência e como resolvê-las

| Dúvida | Prova necessária | Consequência enquanto desconhecida |
| --- | --- | --- |
| Por que o Lovable é fácil para esses profissionais? | Observar participantes realizando criação, ajuste e entrega em sessão autenticada | Tratar explicação de facilidade como hipótese |
| Como funcionam revisões e retomada nos cinco produtos? | Cenários autenticados com material fictício e autorização adequada | Não alegar equivalência funcional ou interna |
| APIs geram entregas suficientemente editáveis? | Spike real e inspeção do resultado no editor/destino | Não prometer suporte de produção |
| Quais formatos e integrações têm prioridade? | Tarefas reais em organizações distintas | Ordem Canva/Gamma/Asana permanece condicional |
| Qual distribuição reduz mais atrito? | Instalação/acesso observado em máquinas de participantes | Não vender o backend local como SaaS pronto |
| O produto reduz trabalho total? | Comparação incluindo revisão, exportação e retrabalho | Não anunciar ganho percentual |

O REA foi usado nesta etapa, mas a inspeção dos fluxos autenticados dos cinco produtos continua pendente. O plano não depende de contornar verificações ou de inventar acesso interno. A próxima coleta, quando houver sessões de teste disponíveis, deve usar cenários declarados e manter seus limites separados das decisões de produto.
