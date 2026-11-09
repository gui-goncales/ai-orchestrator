# Retomada após limite de rodadas

27/10/2026. A tarefa cac04c2c57ea terminou com 25 rodadas persistidas e nenhuma ação pendente. O limite antigo comparava o contador total ao máximo de 25, impedindo qualquer progresso nas retomadas.

AgentRunner agora limita rodadas por chamada de run. O contador acumulado continua crescendo, preservando a identidade das ações no journal. Ações pendentes continuam sendo processadas antes de novos turnos; ações confirmadas não são repetidas por essa mudança.

Ao esgotar o orçamento, o runtime persiste o estado, emite execution_budget_exhausted e retorna interrupted com orientação para retomar. Não declara sucesso nem inicia outra chamada automaticamente. Tempo máximo, cancelamento e verificações de conclusão permanecem ativos.

Regressão: três execuções com orçamento de uma rodada realizam escrita, comando e finish sucessivamente, com contador acumulado 1/2/3 e apenas uma execução de cada ação. O teste de artefato preexistente continua impedindo sucesso fictício, agora esperando interrupted em vez de failed.
