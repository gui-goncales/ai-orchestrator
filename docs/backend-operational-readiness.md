# Backend identity, readiness and safe restart

The backend acquires an exclusive POSIX file lock (`&lt;absolute-database-path&gt;.lock`) before creating the Store, running schema migrations, initializing the Supervisor or recovering interrupted tasks. The `--data` argument is normalized to an absolute path. A second process using the same database is rejected before touching SQLite. The lock is released on initialization errors and normal shutdown. This lock protects cooperating backend instances using this application, not arbitrary SQLite clients.

`GET /api/health` preserves `app`, `status`, `pid` and `time`, and adds `started_at`, `loaded_version`, `disk_version`, `restart_required` and `readiness`. `loaded_version` is a frozen SHA-256 fingerprint of backend Python source files captured at service initialization; `disk_version` is recomputed for each health request. This includes uncommitted source edits and added modules. It is a source snapshot, not a proof of the precise bytecode loaded if source files change during startup.

The schema check opens the existing SQLite database in read-only mode, checks `execution_states`, `tool_actions` and the `tool_actions.evidence` column, and does not perform migrations. `status=online` indicates that the HTTP process is responding; `readiness.status=degraded` and `readiness.persistent_resume=false` indicate that durable resume is not currently verified. An older backend without diagnostic fields is reported by the UI as having unavailable diagnostics rather than being treated as compatible.

## Safe restart

1. Inspect `/api/health` and the dashboard warning. Do not interpret `online` alone as proof that durable resume is ready.
2. Wait for active operations to complete. Preserve the database and its WAL/SHM files. Avoid forcing a restart during file writes or tool actions.
3. Stop the existing backend gracefully and wait for it to exit and release the lock.
4. Start the updated backend using the same `--data` path and normal service command. Do not delete the lock file as a way of bypassing an active instance.
5. Verify `/api/health`: `restart_required=false`, `readiness.status=ready`, `readiness.schema_compatible=true`, and `readiness.persistent_resume=true`. If degraded, inspect `readiness.issues` and resolve the cause before trusting resume.

The dashboard never restarts the backend automatically. No shared service or real production database was restarted or migrated while implementing these diagnostics.

## Verificação conservadora da identidade carregada

O `loaded_version` é um fingerprint congelado dos arquivos no início da construção de `ProcessIdentity`, não uma garantia isolada de que esses arquivos foram importados. A verificação compara assinaturas de funções e métodos já carregados com o código-fonte atual, inspeciona constantes literais e compara o fingerprint antes e depois da inicialização. Divergências, módulos importados tardiamente cuja origem ou código não possa ser verificado, ou impossibilidade de verificar a identidade resultam em `identity_verified: false`, `restart_required: true` e `readiness.status: degraded`. O endpoint preserva os campos existentes.

Limitação: introspecção não comprova de forma absoluta efeitos colaterais de importação, atribuições dinâmicas, monkeypatches nem mudanças transitórias revertidas entre observações. Portanto, o fingerprint de disco nunca deve ser tratado sozinho como prova da versão executada. A operação segura exige reinicialização manual quando a identidade não é verificável; nenhum teste deve reiniciar o serviço nem modificar o banco real.

Validação: `python3 -m unittest discover -s tests -q`, `cd frontend && npm test && npm run build`, `git diff --check`.

Importações tardias legítimas, cujo arquivo já integrava o fingerprint inicial e cujo código corresponde ao código carregado, são aceitas. A verificação continua conservadora para mudanças no disco e módulos iniciais substituídos. A inspeção do schema verifica todas as colunas obrigatórias de cada tabela, sem criar ou alterar o banco. O teste de integração sobe um servidor HTTP isolado com banco temporário e provedor simulado, consulta `/api/health` antes e depois de uma operação HTTP, e encerra apenas o processo de teste.
