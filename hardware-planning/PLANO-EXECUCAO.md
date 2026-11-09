# Plano de execução — agente local com colaboração de modelos conectados

Data: 28/10/2026. Este documento planeja a implementação; não instala dependências, baixa pesos, inicia serviços, chama provedores ou altera configurações existentes.

## 1. Decisão de modelo e arquitetura

**Modelo inicial escolhido: Qwen3.5-4B, quantização Q4_K_M, via Ollama local.**

O alvo é o MacBook Pro M3, GPU de 10 núcleos e 16 GB de memória unificada. Para este sistema híbrido, priorizamos margem operacional enquanto navegador, backend e testes executam. A escolha é uma recomendação de engenharia; ainda não há benchmark local deste modelo. Não equivale a afirmar que ele é o melhor modelo de programação em termos absolutos.

A página oficial do Ollama lista aproximadamente 3,3 GB para a variante Q4_K_M do 4B, incluindo os artefatos distribuídos. Esse tamanho não representa a memória total durante execução. O 9B equivalente aparece com aproximadamente 6,6 GB. O manifesto pode mudar: registrar versão do runtime, backend efetivo, quantização e digest exato no momento da instalação, sem depender de `latest`.

O Ollama foi escolhido pelo servidor local e protocolo de ferramentas documentado. Não reutilizar diretamente o classificador MLX como agente de desenvolvimento. O módulo Decision existente permanece independente.

**Alternativa posterior:** avaliar Qwen3.5-9B Q4_K_M se o 4B não atingir a qualidade necessária e houver margem real de memória. A promoção depende de benchmark com a mesma carga de aplicativos e tarefas, não apenas de conseguir carregar os pesos.

Arquitetura:

```text
Interface → supervisor e política → agente local → executor de ferramentas
                    ↓                    ↑                 ↓
           especialistas conectados      └──── resultados/testes
                    ↓
          proposta ou revisão estruturada
```

Há um único responsável pela escrita em cada tarefa. Revisores retornam propostas; o executor autorizado aplica as alterações. Não colocar modelos concorrentes alterando o mesmo checkout.

## 2. Condições iniciais do piloto

- Servidor restrito ao loopback; nenhuma exposição automática à rede.
- Um modelo local carregado e uma tarefa de geração por vez.
- Entrada somente textual inicialmente; visão é uma etapa futura.
- Contexto inicial de 4.096 tokens totais, com orçamento explícito para saída e ferramentas. Avaliar 8.192 somente após medir recursos.
- Manter requisitos, permissões e objetivo; selecionar arquivos e resumir histórico com referências. Não truncar silenciosamente conteúdo obrigatório.
- Orçamento inicial: 12 chamadas de ferramenta por tarefa, duas tentativas locais de correção e até duas chamadas externas (ajuda e revisão). São parâmetros do piloto, sujeitos a avaliação.
- Timeout e cancelamento por etapa. Encerrar com estado incompleto e checkpoint quando o orçamento se esgotar.
- Conferir suporte da versão exata do Ollama ao modelo, ao backend do Mac e ao ciclo de ferramentas antes de integrar.

## 3. Fase 0 — inventário e avaliação de referência

Estimativa: 0,5–1 dia de trabalho.

1. Mapear adaptadores e provedores efetivamente disponíveis, capacidades, autenticação, cotas e formatos de resposta. Cadastro ou login não comprovam execução real.
2. Inspecionar `backend/agent_engine.py`, `agent_contract.py`, `api_providers.py`, `core.py`, `policy.py` e o fluxo de continuidade.
3. Registrar comportamento atual e executar verificações pertinentes antes das alterações.
4. Preparar 20 tarefas pequenas em repositórios de teste: leitura, criação, edição, movimentação, exclusão, bugs, testes e recuperação.
5. Reservar dez tarefas para avaliação final, sem usá-las para ajustar prompts.

Entrega: matriz de capacidades e resultados de referência. Não fazer chamadas pagas ou enviar código privado durante inventário sem escopo de execução definido.

## 4. Fase 1 — validar inferência e ferramentas locais

Estimativa: 0,5–1 dia.

1. Instalar o runtime e baixar somente o modelo escolhido quando a implementação for autorizada.
2. Registrar digest, tamanho, licença e configuração; manter o modelo carregado entre etapas da tarefa.
3. Testar resposta simples, chamada de ferramenta, retorno de ferramenta e continuação de resposta.
4. Medir carregamento, tempo até primeira saída, geração, memória, pressão de memória e variação de swap.
5. Repetir com navegador, orquestrador e uma verificação de projeto abertos.

Aceite: cinco ciclos consecutivos de ferramenta em fixture concluídos; sem falha por memória ou pressão crítica sustentada. Se falhar, reduzir contexto e carga; não compensar com swap intenso. Não habilitar edição real nesta etapa.

## 5. Fase 2 — adaptador e ciclo de agente

Estimativa: 1–2 dias.

1. Criar adaptador específico para Ollama, inicialmente com `/api/chat`, evitando reabrir indiscriminadamente o cadastro genérico de URLs.
2. Normalizar texto, chamadas de ferramenta, resultados, término, erros e métricas em um contrato interno.
3. Preservar identificação e ordem das chamadas. Aceitar somente ferramentas registradas e argumentos validados.
4. Reutilizar o executor existente; não criar outro caminho de escrita que ignore permissões.
5. Implementar timeout, cancelamento, limites de saída, checkpoint e detecção de tentativas repetidas.
6. Tornar o provedor selecionável, com estados instalado, disponível, indisponível e validação necessária.

Aceite: tarefa de leitura ponta a ponta, recuperação após interrupção e rejeição de ferramenta desconhecida. Resposta final deve distinguir trabalho concluído de trabalho apenas proposto.

## 6. Fase 3 — operações de arquivos e verificações

Estimativa: 1–2 dias.

O código consultado já contém listagem, leitura, busca, escrita, edição, exclusão e execução de comandos em `WorkspaceTools`. Validar e estender esse caminho; não assumir que todas as operações solicitadas estão completas. Não foi localizada uma ferramenta dedicada de movimentação no inventário inicial.

1. Conferir limites de projeto, caminhos relativos, symlinks e grants para cada ferramenta.
2. Acrescentar movimentação/renomeação explícita, com destino existente rejeitado por padrão e política documentada para diretórios e colisões.
3. Exigir precondição de versão/hash para editar, excluir ou mover um arquivo já lido, detectando alterações concorrentes.
4. Implementar registro de operações e recuperação de conteúdo e caminhos, incluindo arquivos não rastreados pelo Git. Restaurar por tarefa; não usar reset global do repositório.
5. Preservar alterações prévias do usuário. Testar interrupção no meio de uma operação e falha na recuperação.
6. Permitir execução somente dentro do contrato autorizado. Validar caminhos não constitui sandbox de sistema operacional: usar isolamento adicional para código não confiável.
7. Alimentar o agente com saída limitada e status real dos testes. Não permitir que texto do modelo seja tratado como comprovação de teste.

Aceite: criar, editar, mover, excluir e restaurar arquivos em fixture; bloquear caminhos externos e permissões ausentes; demonstrar preservação das mudanças prévias do usuário.

## 7. Fase 4 — colaboração com modelos conectados

Estimativa: 1–2 dias.

Papéis iniciais:

| Papel | Responsabilidade |
|---|---|
| Modelo local | Pesquisa delimitada, alterações pequenas e correções orientadas por testes |
| Especialista conectado | Planejamento complexo, diagnóstico após bloqueio e contexto maior |
| Revisor conectado | Examinar diff, requisitos e evidências; propor correções |
| Supervisor | Roteamento, permissões, orçamento, persistência e critérios de conclusão |

Não escolher o especialista apenas pelo nome comercial. Comparar os provedores disponíveis nas tarefas de referência, custo/quota, latência e capacidade de receber contexto. Usar somente integrações comprovadas e autorizadas; uma conexão web pode não oferecer o mesmo contrato de uma API.

Regras iniciais de encaminhamento:

- Tarefa pequena e dentro do contexto: iniciar localmente.
- Contexto necessário maior que o disponível, migração ampla ou arquitetura complexa: especialista planeja antes da execução.
- Duas tentativas locais sem progresso verificável, ferramenta malformada repetida ou regressão persistente: pedir ajuda.
- Revisão externa nas primeiras tarefas com escrita; depois avaliar revisão seletiva por risco e histórico medido.
- Modelo indisponível ou cota esgotada: registrar bloqueio ou continuar apenas no escopo local viável; não trocar silenciosamente de provedor.

Pacote de colaboração: objetivo, critérios de aceite, permissões, trechos necessários, diff, erros e testes executados. Não incluir segredos, histórico irrelevante ou repositório inteiro por padrão. Autorização local não implica autorização para enviar arquivos a um provedor externo; a política por projeto deve definir isso.

O revisor retorna achados e propostas. A conclusão depende das evidências e dos critérios de aceite; concordância entre dois modelos não comprova correção.

Aceite: demonstrar fluxo local, ajuda após bloqueio, revisão, indisponibilidade externa e respeito ao orçamento, com rastreabilidade de qual provedor recebeu quais dados.

## 8. Fase 5 — memória e conhecimento novo

Estimativa: 1–2 dias.

1. Salvar decisões confirmadas por projeto, com origem, data, evidência e possibilidade de correção.
2. Recuperar documentação e trechos relevantes por busca; adicionar embeddings somente se a comparação demonstrar necessidade.
3. Separar instruções do usuário, dados recuperados e conteúdo não confiável.
4. Invalidar referências quando arquivos ou documentação mudarem.
5. Mostrar quando uma recomendação se baseia em informação antiga ou não verificada.

Aceite: retomar uma tarefa em nova sessão e recuperar a convenção correta; atualizar uma decisão obsoleta; não misturar memória entre projetos.

## 9. Fase 6 — avaliação e ativação gradual

Estimativa: 1–2 dias.

Comparar três configurações com tarefas equivalentes e fixtures restauradas: local, conectado e híbrido. Registrar quantização, digest, contexto e versão do código. Amostras pequenas orientam o piloto; não sustentam afirmações gerais de superioridade.

Métricas: tarefas corretas, regressões, intervenções humanas, arquivos afetados, chamadas inválidas, tempo total, memória, chamadas externas e custo ou consumo de cota conhecido. Não inventar custo quando o provedor não o informa.

Critérios provisórios para liberar o piloto:

- Nenhuma violação de permissão nos testes de fronteira; uma falha bloqueia a ativação.
- Recuperação demonstrada para todas as operações de arquivo do piloto.
- Pelo menos 8 de 10 tarefas reservadas concluídas com critérios objetivos; analisar individualmente as falhas.
- Sem regressão nos fluxos existentes cobertos pelas verificações pertinentes.
- Exibir origem das respostas, encaminhamentos, falhas e verificações no painel.
- A qualidade do híbrido deve justificar seu custo/tempo comparada ao conectado sozinho. Se não justificar, ajustar papéis ou manter local em tarefas menores.

Ativar por provedor/projeto com flag e reversão independente. Começar com fixture, depois projeto de teste, depois projetos reais autorizados. Não mudar automaticamente o padrão de todos os projetos.

## 10. Treinamento futuro — fora do primeiro piloto

Coletar exemplos somente com política explícita de retenção. Registrar entrada, tentativa, correção, evidência e aceite. Remover segredos e verificar condições do provedor antes de utilizar saídas para treinamento.

Após reunir exemplos revisados suficientes de uma tarefa recorrente, planejar LoRA/QLoRA separado. Separar dados por projeto/origem e manter teste inédito. Registrar compatibilidade do adaptador com arquitetura, revisão do modelo e runtime; formato MLX não deve ser presumido diretamente utilizável no Ollama.

Só promover modelo ajustado se melhorar tarefas reservadas sem regressões materiais. Conversas salvas e colaboração entre modelos não atualizam automaticamente os pesos.

## 11. Prazo e recursos

As fases somam aproximadamente **7–13 dias de trabalho**, sem garantia, dependendo dos problemas encontrados e da disponibilidade dos provedores. Custos de chamadas externas e eventuais assinaturas serão definidos após inventário; não há orçamento implícito ilimitado.

Não comprar hardware no piloto. Avaliar 9B ou hardware maior após medir o 4B no fluxo real. A meta é um agente local útil com especialistas externos, e não autonomia geral garantida.

## 12. Ordem de implementação

1. Inventário e tarefas de referência.
2. Validação local do Qwen3.5-4B Q4_K_M.
3. Adaptador e ciclo de ferramentas.
4. Operações de arquivos e recuperação.
5. Encaminhamento e revisão com modelos conectados.
6. Memória e documentação recuperável.
7. Avaliação reservada e ativação por projeto.
8. Decidir sobre 9B, novo hardware e treinamento com base em resultados.

## Fontes consultadas

- [Modelo oficial Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B)
- [Variante Ollama 4B e Q4_K_M](https://ollama.com/library/qwen3.5:4b)
- [Variante Ollama 9B e Q4_K_M](https://ollama.com/library/qwen3.5:9b)
- [Ciclo de ferramentas do Ollama](https://docs.ollama.com/capabilities/tool-calling)
- Código e documentação locais: `backend/agent_engine.py`, `backend/agent_contract.py`, `backend/core.py`, `backend/api_providers.py`, `docs/DECISION-LOCAL.md` e `docs/API-PROVIDERS.md`.

Estado desta entrega: apenas plano documentado. Compatibilidade ponta a ponta, qualidade e desempenho ainda serão comprovados durante a execução futura.
