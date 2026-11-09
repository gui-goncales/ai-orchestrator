# Planejamento de hardware para IA local de desenvolvimento

Este documento reúne meu objetivo e contexto para que outra IA me ajude a escolher hardware. É um material de planejamento independente: não autoriza instalar, comprar, treinar, executar modelos ou modificar o AI Orchestrator.

Data de referência: 28/10/2026. Preços, modelos e compatibilidade devem ser verificados novamente na data da análise.

## Pedido para a IA que receber este documento

Quero ajuda para escolher hardware para executar uma IA local eficaz em desenvolvimento de software, integrada ao meu orquestrador. Quero entender as alternativas, limitações, custos e possibilidades de expansão antes de comprar.

Não presuma meu orçamento. Primeiro apresente opções por faixas de investimento e explique os compromissos. Faça perguntas sobre as informações ausentes e pesquise fontes oficiais atuais. Diferencie resultados medidos, especificações oficiais e estimativas.

Não quero apenas saber se um modelo cabe na memória: quero saber se a configuração oferece qualidade, velocidade e contexto suficientes para trabalhar em projetos reais.

## Objetivo

Quero um agente capaz de:

- Entender requisitos e a estrutura de um repositório.
- Pesquisar, ler, criar, editar, excluir, mover e renomear arquivos.
- Atualizar imports e referências após reorganizar arquivos.
- Implementar funcionalidades, corrigir bugs e refatorar vários arquivos.
- Executar testes, builds, lint e outros comandos autorizados.
- Interpretar erros, corrigir a implementação e verificar novamente.
- Consultar documentação nova e usar bibliotecas que não conhecia previamente.
- Preservar decisões, convenções e conhecimento de cada projeto entre sessões.
- Permitir ajuste fino futuro, quando houver dados e uma necessidade comprovada.

Quero a melhor qualidade de desenvolvimento que faça sentido para meu investimento. Ainda preciso decidir se priorizarei execução integralmente local ou uma arquitetura híbrida.

## Equipamento atual

Especificações consultadas na máquina em 28/10/2026:

| Item | Configuração |
|---|---|
| Computador | MacBook Pro com Apple M3 |
| CPU | 8 núcleos: 4 de desempenho e 4 de eficiência |
| GPU | 10 núcleos, com suporte a Metal |
| Memória | 16 GB de memória unificada LPDDR5 |
| Espaço disponível na consulta | Aproximadamente 331 GiB |

A memória é compartilhada entre sistema, aplicativos e GPU. Não há 16 GB exclusivos para o modelo. O espaço disponível varia com o uso.

Posso considerar manter esse Mac como interface e estação de trabalho, usando outra máquina como servidor de inferência. A possibilidade ainda deve ser comparada com substituir o computador ou utilizar nuvem.

## Contexto do AI Orchestrator

Meu projeto tem frontend React/TypeScript, backend Python e persistência SQLite. Sua proposta é gerenciar agentes, contexto, ferramentas, histórico e execução de tarefas.

Na inspeção anterior do código e da documentação:

- Existe um módulo de inferência local baseado em MLX, destinado a decisões delimitadas.
- A documentação registra uso de `mlx-community/Qwen3-4B-Instruct-2507-4bit`, aproximadamente 2,1 GiB em disco.
- Esse caminho classifica alternativas e não equivale a um agente completo de desenvolvimento.
- O modo documentado é de observação (`shadow`); não se deve presumir que ele esteja ativo sem verificar o processo.
- Existe código de API compatível com OpenAI, mas a documentação informa que o cadastro genérico está desabilitado no supervisor.
- Integrar um agente local completo exigirá trabalho de software, independentemente da compra de hardware.

O orquestrador deve administrar ferramentas e permissões. O modelo propõe chamadas; o executor realiza as operações autorizadas e devolve os resultados.

Fluxo desejado:

```text
Pedido → pesquisa no projeto → planejamento → alteração de arquivos
       → testes/build → análise dos resultados → correções → revisão
```

O sistema deve permitir checkpoints e recuperação de alterações, inclusive considerando arquivos não rastreados pelo Git. Permissões não devem depender apenas da interpretação do modelo.

## O que significa aprender

Preciso distinguir três mecanismos:

| Mecanismo | Finalidade | Atualiza os pesos? |
|---|---|---|
| Consulta e RAG | Buscar código e documentação relevantes e atuais | Não |
| Memória persistente | Recuperar decisões, preferências e convenções do projeto | Não |
| Ajuste fino com LoRA/QLoRA | Ensinar padrões recorrentes a partir de exemplos revisados | Sim |

Não espero que salvar conversas atualize os pesos automaticamente. Também não quero treinamento indiscriminado com respostas que podem estar erradas.

Treinamento do zero de um modelo competitivo não é o objetivo. A prioridade é inferência eficaz; ajuste fino é uma capacidade futura a dimensionar separadamente.

## Modelos citados como candidatos, não como ranking definitivo

| Modelo | Papel na discussão |
|---|---|
| Qwen3.5-4B em 4 bits | Opção com mais margem de memória no Mac atual |
| Qwen3.5-9B em 4 bits | Candidato a avaliar no Mac atual, com memória e contexto controlados |
| Qwen3-Coder-30B-A3B-Instruct | Candidato especializado em programação com ferramentas para hardware maior |
| Devstral Small 2 24B | Outro candidato de desenvolvimento a pesquisar e comparar |

Essa lista não comprova qual é o melhor modelo disponível. Quero que a análise atualize os candidatos, confirme suporte ao runtime escolhido e compare programação com ferramentas, qualidade em repositórios e limites práticos.

Em modelos MoE, parâmetros ativos não equivalem ao total de pesos que precisam ser armazenados. Por exemplo, um modelo com 30B totais e 3B ativos não tem o consumo de memória de um modelo denso de 3B.

Uma conta simplificada de pesos em 4 bits é `parâmetros × 0,5 byte`. Ela não inclui metadados de quantização, cache de contexto, buffers e memória do runtime. Não usar essa conta como requisito total de RAM ou VRAM.

## Comparações de hardware que eu preciso

Quero comparar pelo menos:

1. Continuar apenas com o Mac M3 de 16 GB.
2. Comprar um Mac com mais memória unificada.
3. Montar um desktop Linux com GPU NVIDIA e usar o Mac como cliente.
4. Usar um servidor local dedicado, avaliando uma ou mais GPUs quando justificável.
5. Usar GPU em nuvem para treinamento ou tarefas mais exigentes.
6. Adotar uma arquitetura híbrida com modelo local e provedor remoto opcional.

Para cada alternativa, informar:

- Configuração completa: CPU, RAM, GPU/VRAM, SSD, fonte, refrigeração e rede quando aplicáveis.
- Custo total estimado no Brasil, em reais, com data e fontes.
- Modelos e quantizações que cabem com margem operacional.
- Contexto utilizável enquanto navegador, IDE, orquestrador e testes estão abertos.
- Latência inicial, velocidade de geração e processamento de entrada, quando houver medições comparáveis.
- Diferença entre um agente e vários agentes simultâneos.
- Capacidade de ajuste fino e suas limitações.
- Consumo elétrico, ruído, calor, expansão, manutenção e garantia.
- Compatibilidade real de software; não presumir equivalência entre CUDA, Metal e outros backends.
- Uso de offload para RAM/CPU e o impacto de desempenho.
- Alternativa de menor custo que ainda cumpra o objetivo.

Ao discutir múltiplas GPUs, explicar que VRAM não se soma automaticamente em qualquer software e que comunicação entre placas pode limitar o desempenho.

## Como avaliar eficácia

Quero comparar modelos e máquinas nas mesmas tarefas representativas:

- Corrigir um bug com teste de regressão relevante.
- Implementar uma funcionalidade que envolva vários arquivos.
- Refatorar preservando comportamento.
- Mover um módulo e atualizar referências.
- Excluir código obsoleto sem quebrar o projeto.
- Consultar documentação nova e utilizar corretamente uma API.
- Retomar uma tarefa após interrupção.

Medir conclusão correta, regressões, intervenções humanas, tempo total, consumo de memória, custo e capacidade de recuperação. Tokens por segundo isoladamente não definem o melhor agente.

Não comparar benchmarks com contextos, quantizações, ferramentas ou critérios diferentes como se fossem equivalentes.

## Custos a separar

- Compra e eventuais upgrades de hardware.
- Energia e armazenamento.
- Integração e manutenção do orquestrador.
- Preparação e revisão de dados para treinamento.
- Computação de treinamento e avaliação.
- Nuvem, tráfego e armazenamento persistente, se utilizados.

O modelo pode não ter cobrança por token na execução local, mas a operação tem custos. Treinar na nuvem e executar localmente é uma opção válida, desde que formato, licença e runtime sejam compatíveis.

## Informações ainda em aberto

- Orçamento inicial e limite mensal aceitável.
- Necessidade de funcionamento totalmente offline.
- Aceitação ou não de enviar código para provedores externos.
- Linguagens, frameworks e tamanho habitual dos repositórios.
- Quantidade de usuários e tarefas simultâneas.
- Tempo de espera aceitável por alteração e por tarefa completa.
- Interesse em máquina portátil ou servidor fixo.
- Frequência e escala pretendidas para ajuste fino.
- Disponibilidade para montar e administrar Linux.
- Restrições de ruído, energia e espaço físico.

## Entrega esperada da análise de hardware

Quero uma recomendação principal e alternativas por orçamento, com justificativa, limitações e caminho de expansão. Diferencie a melhor máquina para inferência da melhor máquina para treinamento. Indique o que posso validar no Mac atual antes de gastar dinheiro e quais medições realmente justificariam uma compra.

Não apresente uma compra como garantia de autonomia ou qualidade. Hardware permite executar modelos maiores e mais rápido; a confiabilidade também depende do modelo, contexto, ferramentas e avaliação.

## Fontes iniciais

- [Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B)
- [Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B)
- [Qwen3-Coder-30B-A3B-Instruct](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct)
- [Devstral e Mistral Vibe](https://mistral.ai/news/devstral-2-vibe-cli)
- [MLX LM](https://github.com/ml-explore/mlx-lm)
- [LoRA/QLoRA com MLX LM](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md)
- [Compatibilidade de API do Ollama](https://docs.ollama.com/api/openai-compatibility)
- [Preços de GPU da Runpod](https://www.runpod.io/pricing)

As fontes são pontos de partida. A análise deve verificar informações atuais, licenças e suporte das versões exatas escolhidas.
