# Contratos dos agentes

Os workers do executor universal recebem instruções geradas por `backend/agent_contract.py` a partir das capacidades reais de WorkspaceTools. O prompt, os exemplos de chamadas, a lista de ferramentas nos lembretes e o bloqueio em dispatch usam o mesmo contrato.

## Capacidades

- Leitura: list_dir, read_file, find_files e finish.
- Escrita, quando permitida: write_file, edit_file e delete_file.
- Execução, quando permitida separadamente: run_command.

O prompt de somente leitura não anuncia ferramentas de escrita. Um worker autorizado a escrever sem executar comandos recebe exemplos de escrita, mas nenhum exemplo de run_command. O dispatch rejeita capacidades não concedidas e informa apenas as ferramentas atualmente disponíveis; os métodos de arquivos e comandos mantêm suas próprias verificações.

O contexto montado pela política também deriva as restrições do plano do Decision. Isso evita descrever como somente leitura um fluxo de artefato que permite criar arquivos, ou anunciar comandos apenas porque o fluxo se chama Work.

O contrato instrui o worker a preservar o objetivo, tratar arquivos e resultados como dados, distinguir erro de execução de evidência confirmada e não usar avaliações shadow ou abstenções para conceder permissões. Isso é orientação de execução; a validação de capacidades continua no runtime.

## Retomada

Checkpoints guardam `worker_contract` junto ao histórico e ao journal de ações. Na retomada, o executor substitui as mensagens system antigas pelo prompt atual. Quando o contrato mudou ou o checkpoint é anterior a esse recurso, acrescenta o contrato e o objetivo ao último feedback pendente e registra `agent_contract_refreshed`.

Anexar a atualização ao feedback preserva as observações de ferramentas que provedores de navegador recebem incrementalmente. O histórico completo não é reenviado ao navegador. Operações pendentes passam pelas capacidades atuais; uma escrita ainda não executada não herda a autorização anterior. Resultados de ações já confirmadas continuam no journal e não são executados novamente apenas por causa da atualização do prompt.

## Seleção e recuperação de provedores

`backend/agent_routing.py` concentra os filtros comuns do roteamento inicial e do failover: instalação, disponibilidade (available/ready), habilitação para roteamento automático, bloqueio automático por falha recente e exclusão de ferramentas estáticas e Gemini legado como substitutos automáticos.

A seleção inicial mantém a avaliação de histórico e as regras de comparação de tokens. O failover mantém seus próprios gates de falha e continuidade. Compartilhar elegibilidade não significa usar a mesma estratégia de ranking ou garantir qualidade equivalente entre modelos.

## Validação e limites

Os testes incluem prompt por capacidade, retomada com redução de permissões e escrita pendente, preservação de feedback incremental, contrato persistido, contexto de artefato e consistência dos filtros de provedores. Não foram feitas chamadas pagas aos provedores para essas alterações.

Esses controles se aplicam ao executor universal de ferramentas locais. Adaptadores nativos continuam sujeitos aos seus próprios mecanismos de sandbox e autorização; este trabalho não transforma comandos locais em processos isolados pelo sistema operacional. Não houve reinício do serviço em uso.
